"""
pdf_utils.py — lightweight PDF tools for the sourcing agent.

The sourcing agent's job, when it sees an arXiv-style research paper, is to
make sure the paper's figures (architecture diagrams, result tables/graphs)
are recorded in topic.json *before* the script agent runs. The script agent
already has its own (heavier) paper-walkthrough pipeline; this is just the
"give me the figure URLs / cached files" part.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import List

import httpx

log = logging.getLogger(__name__)

try:
    import fitz  # type: ignore  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Domain → URL pattern that identifies a paper page. The capture group, when
# present, is the canonical paper id we use to derive the PDF URL.
_PAPER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("arxiv", re.compile(r"https?://arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})")),
    ("acl", re.compile(r"https?://aclanthology\.org/([^/]+)/?")),
    ("openreview", re.compile(r"https?://openreview\.net/(?:forum|pdf)\?id=([^&]+)")),
    ("ar5iv", re.compile(r"https?://ar5iv\.labs\.arxiv\.org/html/(\d{4}\.\d{4,5})")),
]


def detect_paper(url: str) -> tuple[str, str] | None:
    """Return (kind, id) when `url` is a recognised research-paper page."""
    for kind, pat in _PAPER_PATTERNS:
        m = pat.match(url)
        if m:
            return kind, m.group(1)
    return None


def paper_pdf_url(kind: str, paper_id: str) -> str | None:
    """Map (kind, paper_id) → direct PDF URL. None if the host has no canonical PDF."""
    if kind in ("arxiv", "ar5iv"):
        return f"https://arxiv.org/pdf/{paper_id}"
    if kind == "acl":
        # ACL anthology PDFs are at /<id>.pdf
        return f"https://aclanthology.org/{paper_id}.pdf"
    if kind == "openreview":
        return f"https://openreview.net/pdf?id={paper_id}"
    return None


def download_pdf(url: str, dest: Path, timeout: int = 30) -> bool:
    """Stream a PDF to `dest`. Returns True on success and a non-tiny file."""
    try:
        with httpx.stream(
            "GET", url, headers={"User-Agent": _USER_AGENT},
            follow_redirects=True, timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return dest.exists() and dest.stat().st_size > 10_000
    except Exception as exc:
        log.debug("PDF download failed for %s: %s", url, exc)
        return False


def extract_pdf_figures(
    pdf_path: Path,
    out_dir: Path,
    max_figures: int = 5,
    min_dim_px: int = 200,
    max_aspect_ratio: float = 6.0,
) -> List[Path]:
    """
    Lift embedded raster figures from a PDF. Pure heuristic — drops tiny
    glyph images, equation strips, and full-page banners (extreme aspect
    ratios). Saves PNG/JPEG to `out_dir/pdf-fig-<NN>.<ext>` and returns
    the new file paths in extraction order.
    """
    if not _HAS_PYMUPDF or not _HAS_PIL or not pdf_path.exists():
        if not _HAS_PYMUPDF:
            log.info("pymupdf not installed — skipping PDF figure extraction")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    seen_xrefs: set[int] = set()

    try:
        doc = fitz.open(str(pdf_path))  # type: ignore
    except Exception as exc:
        log.debug("PyMuPDF open failed: %s", exc)
        return []

    try:
        for page_idx, page in enumerate(doc):
            for info in page.get_images(full=True):
                xref = info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    base_img = doc.extract_image(xref)
                    ext = base_img.get("ext", "png")
                    img_bytes = base_img.get("image")
                    if not img_bytes:
                        continue
                    try:
                        pil = Image.open(io.BytesIO(img_bytes))
                        w, h = pil.size
                    except Exception:
                        continue
                    if min(w, h) < min_dim_px:
                        continue
                    if (
                        w / max(h, 1) > max_aspect_ratio
                        or h / max(w, 1) > max_aspect_ratio
                    ):
                        continue
                    # Heuristic: arXiv title pages often embed 512×512 (or similar
                    # small perfect-square) decorative images. Real research
                    # figures are wider than tall, taller than wide, or just
                    # bigger than 600×600. Drop tiny squares on the first page.
                    if (
                        page_idx == 0
                        and w == h
                        and w <= 600
                    ):
                        continue
                    dest = out_dir / f"pdf-fig-{len(saved):02d}.{ext}"
                    dest.write_bytes(img_bytes)
                    saved.append(dest)
                    log.info(
                        "✅ PDF figure: %s (%dx%d, page %d)",
                        dest.name, w, h, page_idx + 1,
                    )
                    if len(saved) >= max_figures:
                        return saved
                except Exception as exc:
                    log.debug("Skipped PDF figure xref %s: %s", xref, exc)
    finally:
        doc.close()

    return saved
