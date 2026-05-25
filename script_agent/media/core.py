# ─── media.py ────────────────────────────────────────────────────────────────
# Media pipeline for script_agent:
#   - Download and quality-check images from topic.json
#   - Extract YouTube thumbnails (or download short clips via yt-dlp)
#   - Generate images with GPT-image-1 for beats that need stronger visuals
#
# All downloaded/generated assets are saved to: <out_dir>/media/

import base64
import io
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from openai import OpenAI
from PIL import Image

# PyMuPDF (optional) — used to extract embedded figures from arXiv PDFs and to
# render the full paper as one tall image for paper_scroll scenes. We import
# lazily inside the helpers so the module still loads if pymupdf is missing.
try:  # pragma: no cover
    import fitz  # type: ignore
    _HAS_PYMUPDF = True
except ImportError:
    fitz = None  # type: ignore
    _HAS_PYMUPDF = False

log = logging.getLogger(__name__)

# ─── Badge / icon URL patterns to skip automatically ─────────────────────────
_SKIP_PATTERNS = [
    "shields.io",
    ".svg",
    "badge",
    "favicon",
    "icon",
    "logo.png",
    "workflows/",     # GitHub action badge URLs
    "github.com/badges",
]


def _is_badge_url(url: str) -> bool:
    low = url.lower()
    return any(p in low for p in _SKIP_PATTERNS)


# ─── Image quality check ──────────────────────────────────────────────────────

def check_and_download_image(url: str, dest: Path) -> bool:
    """
    Download an image to `dest`. Returns True if the image is usable
    (large enough, not a badge/icon). The file is NOT saved if unusable.
    """
    if _is_badge_url(url):
        log.debug("Skipping badge URL: %s", url)
        return False

    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            log.debug("HTTP %s for %s", resp.status_code, url)
            return False

        content_type = resp.headers.get("content-type", "")
        if "svg" in content_type:
            return False

        img = Image.open(io.BytesIO(resp.content))
        w, h = img.size

        # Reject tiny images (under 200px on either side — almost always icons)
        if min(w, h) < 200:
            log.debug("Too small (%dx%d): %s", w, h, url)
            return False
        # Reject extreme aspect ratios (banners / 1xN ligatures from PDF assets)
        if w / max(h, 1) > 6 or h / max(w, 1) > 6:
            log.debug("Badge-like aspect ratio (%dx%d): %s", w, h, url)
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        log.info("✅ Image saved: %s (%dx%d)", dest.name, w, h)
        return True

    except Exception as exc:
        log.debug("Image check failed for %s: %s", url, exc)
        return False


# ─── YouTube helpers ──────────────────────────────────────────────────────────

def extract_youtube_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def get_youtube_thumbnail(url: str, dest: Path) -> bool:
    """Download the maxresdefault (or hqdefault fallback) thumbnail."""
    vid_id = extract_youtube_id(url)
    if not vid_id:
        return False

    for quality in ("maxresdefault", "hqdefault", "mqdefault"):
        thumb_url = f"https://img.youtube.com/vi/{vid_id}/{quality}.jpg"
        if check_and_download_image(thumb_url, dest):
            return True
    return False


def get_video_metadata(url: str) -> dict | None:
    """Use yt-dlp to get video metadata (duration, title) without downloading."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-playlist",
                "--socket-timeout", "20",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception as exc:
        log.debug("yt-dlp metadata failed for %s: %s", url, exc)
    return None


def _direct_download_video(url: str, dest: Path) -> bool:
    """Download a static .mp4/.webm/.mov directly via httpx (no yt-dlp)."""
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            if resp.status_code != 200:
                log.debug("Direct video HTTP %s for %s", resp.status_code, url)
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(1024 * 256):
                    f.write(chunk)
        if dest.exists() and dest.stat().st_size > 10_000:
            log.info("✅ Video downloaded direct: %s (%.1f MB)",
                     dest.name, dest.stat().st_size / 1_048_576)
            return True
        return False
    except Exception as exc:
        log.debug("Direct video download error for %s: %s", url, exc)
        return False


def download_video_clip(url: str, dest: Path, max_sec: int = 90) -> bool:
    """
    Download a video clip. Fast path: if the URL is a static .mp4/.webm/.mov,
    fetch directly via httpx. Otherwise fall back to yt-dlp (handles YouTube,
    Vimeo, Twitter, etc.) trimmed to the first `max_sec` seconds.
    Saves to dest (must end in .mp4).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Fast path for direct video URLs (Netlify, S3, blog assets) where yt-dlp
    # can't parse duration metadata.
    lowered = url.split("?")[0].lower()
    if any(lowered.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v")):
        if _direct_download_video(url, dest):
            return True
        # Fall through to yt-dlp as a backup

    try:
        result = subprocess.run(
            [
                "yt-dlp", url,
                "-o", str(dest),
                "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
                "--external-downloader", "ffmpeg",
                "--external-downloader-args", f"ffmpeg_i:-ss 0 -to {max_sec}",
                "--merge-output-format", "mp4",
                "--no-playlist",
                "--socket-timeout", "30",
                "-q",
            ],
            timeout=180,
            capture_output=True,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 10_000:
            log.info("✅ Video clip saved: %s", dest.name)
            return True
        log.debug("yt-dlp download failed (rc=%s): %s", result.returncode, url)
        return False
    except Exception as exc:
        log.debug("Video download error for %s: %s", url, exc)
        return False


# ─── GPT image generation ─────────────────────────────────────────────────────

def generate_image(prompt: str, dest: Path, openai_api_key: str) -> bool:
    """
    Generate an image with GPT-image-1 and save it to dest.
    Returns True on success.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="medium",
        )
        # gpt-image-1 returns b64_json by default
        image_data = response.data[0]
        if hasattr(image_data, "b64_json") and image_data.b64_json:
            dest.write_bytes(base64.b64decode(image_data.b64_json))
        elif hasattr(image_data, "url") and image_data.url:
            img_bytes = httpx.get(image_data.url, timeout=30).content
            dest.write_bytes(img_bytes)
        else:
            return False

        log.info("✅ Generated image: %s", dest.name)
        return True

    except Exception as exc:
        log.warning("GPT image generation failed: %s", exc)
        return False


# ─── Source page scraping ─────────────────────────────────────────────────────
# When a topic has only a thin set of images (e.g. just a GitHub repo card or
# a single OG image), we visit the source page itself and harvest the rich
# inline visuals: README images for GitHub, article body images / og:image
# variants for news sites, etc. This dramatically broadens the visual palette
# the narrative LLM has to work with without any hand-curation.

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
_MAX_SCRAPED_IMAGES = 12


def _normalise_image_url(url: str, page_url: str) -> str | None:
    """Resolve relative URLs and strip GitHub camo wrappers / fragment hashes."""
    if not url:
        return None
    url = url.strip()
    # Strip fragment (e.g. ?raw=true#gh-light-mode-only)
    url = url.split("#", 1)[0]
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin(page_url, url)
    elif not url.startswith(("http://", "https://")):
        url = urljoin(page_url, url)
    return url


def _is_arxiv(url: str) -> str | None:
    """Return the arXiv id (e.g. '2605.00833') if the URL is an arXiv paper page, else None."""
    m = re.match(r"https?://arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else None


def fetch_arxiv_pdf(arxiv_id: str, dest: Path) -> bool:
    """Download the arXiv PDF for `arxiv_id` to `dest`. Returns True on success."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        with httpx.stream(
            "GET",
            pdf_url,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as resp:
            if resp.status_code != 200:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception as exc:
        log.debug("arXiv PDF download failed for %s: %s", arxiv_id, exc)
        return False


def extract_pdf_figures(pdf_path: Path, out_dir: Path, max_figures: int = 8) -> list[Path]:
    """
    Extract embedded raster figures from a PDF using PyMuPDF.

    Skips tiny images (<200px on either side) since arXiv PDFs sometimes
    contain ligature glyphs or paper logos as 1×N images.
    """
    if not _HAS_PYMUPDF or not pdf_path.exists():
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    seen_xrefs: set[int] = set()

    try:
        doc = fitz.open(str(pdf_path))  # type: ignore
    except Exception as exc:
        log.debug("PyMuPDF open failed: %s", exc)
        return []

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
                # Validate dimensions via Pillow
                try:
                    pil = Image.open(io.BytesIO(img_bytes))
                    w, h = pil.size
                except Exception:
                    continue
                if min(w, h) < 200:
                    continue
                if w / max(h, 1) > 6 or h / max(w, 1) > 6:
                    continue
                dest = out_dir / f"pdf-fig-{len(saved):02d}.{ext}"
                dest.write_bytes(img_bytes)
                saved.append(dest)
                log.info("✅ PDF figure: %s (%dx%d, page %d)", dest.name, w, h, page_idx + 1)
                if len(saved) >= max_figures:
                    doc.close()
                    return saved
            except Exception as exc:
                log.debug("Skipped PDF figure xref %s: %s", xref, exc)

    doc.close()
    return saved


_KNOWN_SECTION_NAMES = {
    "abstract", "introduction", "related work", "background",
    "method", "methods", "methodology", "approach",
    "experiments", "experimental setup", "evaluation",
    "results", "discussion", "analysis", "ablation", "ablations",
    "limitations", "conclusion", "conclusions", "future work",
    "references", "acknowledgments", "acknowledgements",
}


def _looks_like_section_header(text: str) -> bool:
    """Heuristic: short numbered or all-caps section header line."""
    s = text.strip()
    if not s or len(s) > 80:
        return False
    s_low = s.lower().rstrip(":.")
    # "1 Introduction", "3.2 Method", etc.
    if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z][\w\- ]+$", s):
        return True
    # Bare known section name
    return s_low in _KNOWN_SECTION_NAMES


def _block_text(block: dict) -> str:
    """Concatenate all spans in a PyMuPDF text block dict."""
    out: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        out.append(" ".join(span.get("text", "") for span in spans).strip())
    return " ".join(s for s in out if s).strip()


def _block_max_font(block: dict) -> float:
    """Return the largest font size within the block (for header detection)."""
    sizes: list[float] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            sizes.append(float(span.get("size", 0)))
    return max(sizes) if sizes else 0.0


def process_paper_pdf(
    pdf_path: Path,
    out_dir: Path,
    width: int = 1080,
    max_pages: int = 14,
    max_anchors: int = 18,
) -> dict | None:
    """
    Render the PDF as one tall PNG suitable for the paper_walkthrough scene
    AND extract a structured outline (title, abstract, sections, figures,
    tables) with absolute Y/X positions in the canvas coordinate system.

    Returns dict:
        {
            "scroll_image_path": Path,
            "image_width": int,
            "image_height": int,
            "full_text": str,
            "anchors": [{id,label,kind,page,y,h,x,w,text}, ...],
            "pages": [{y_offset, height, zoom, page_w_pts, page_h_pts}, ...],
        }
    """
    if not _HAS_PYMUPDF or not pdf_path.exists():
        return None
    try:
        doc = fitz.open(str(pdf_path))  # type: ignore
    except Exception as exc:
        log.debug("PyMuPDF open failed: %s", exc)
        return None

    page_imgs: list[Image.Image] = []
    page_records: list[dict] = []   # bookkeeping for canvas-coord conversion
    full_text_parts: list[str] = []
    raw_blocks_per_page: list[list[dict]] = []  # collected for anchor pass

    # ── Pre-pass: find content bounding box in PDF-point space ───────────────
    # Academic papers have wide margins. We detect the leftmost and rightmost
    # text column boundaries across the first few pages, then clip the render
    # to that content box and zoom to fill `width` pixels. This removes the
    # white margins and makes the content readable at full screen width.
    content_lefts: list[float] = []
    content_rights: list[float] = []
    first_page_w_pts: float = 612.0  # letter-size fallback
    for i, page in enumerate(doc):
        if i >= min(max_pages, 5):
            break
        first_page_w_pts = page.rect.width
        page_h_pts_local = page.rect.height
        try:
            blocks_raw = page.get_text("blocks")
        except Exception:
            blocks_raw = []
        # Each block: (x0, y0, x1, y1, text, block_no, block_type)
        # block_type 0 = text, 1 = image
        # We filter out arXiv-style watermarks (narrow tall blocks pinned to
        # the right margin) before computing the content bbox, otherwise the
        # rendered paper looks left-skewed because the right column is just
        # "arXiv:1234.56789 [cs.LG] 12 May 2026" rotated 90°.
        text_blocks = []
        for b in blocks_raw:
            if b[6] != 0 or not b[4].strip():
                continue
            x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
            width_pt = x1 - x0
            height_pt = y1 - y0
            rel_left = x0 / max(first_page_w_pts, 1.0)
            # 1) arXiv watermark: tall narrow block in the right margin
            if rel_left > 0.85 and height_pt > 0.35 * page_h_pts_local:
                continue
            # 2) Narrow side bands (page numbers, side captions)
            if width_pt < 30 and rel_left > 0.85:
                continue
            # 3) Mirror filters on the LEFT margin in case the watermark is there
            rel_right = x1 / max(first_page_w_pts, 1.0)
            if rel_right < 0.15 and height_pt > 0.35 * page_h_pts_local:
                continue
            if width_pt < 30 and rel_right < 0.15:
                continue
            text_blocks.append(b)
        if text_blocks:
            content_lefts.append(min(b[0] for b in text_blocks))
            content_rights.append(max(b[2] for b in text_blocks))

    if content_lefts:
        # Use the minimum left / maximum right across sampled pages for
        # the widest content region (e.g. two-column figures on page 2+).
        content_left_pts: float = max(0.0, min(content_lefts) - 10.0)
        content_right_pts: float = min(first_page_w_pts, max(content_rights) + 10.0)
    else:
        content_left_pts = 0.0
        content_right_pts = first_page_w_pts

    content_w_pts = max(content_right_pts - content_left_pts, 1.0)
    log.debug(
        "PDF content bbox: x=[%.1f, %.1f] pts  (page_w=%.1f)",
        content_left_pts, content_right_pts, first_page_w_pts,
    )

    cumulative_y = 0
    for i, page in enumerate(doc):
        if i >= max_pages:
            break

        page_w_pts = page.rect.width
        page_h_pts = page.rect.height
        # Zoom so that the content column fills `width` pixels exactly.
        zoom = width / content_w_pts

        clip = fitz.Rect(content_left_pts, 0, content_right_pts, page_h_pts)  # type: ignore
        mat = fitz.Matrix(zoom, zoom)  # type: ignore
        pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # Snap width precisely to canvas width after floating-point zoom.
        rendered_w = img.width
        rendered_h = img.height
        if rendered_w != width:
            new_h = int(rendered_h * (width / rendered_w))
            img = img.resize((width, new_h), Image.LANCZOS)
            rendered_h = new_h

        # eff_zoom converts PDF y-coordinates to canvas pixels.
        eff_zoom = width / content_w_pts

        page_imgs.append(img)
        page_records.append(
            {
                "y_offset": cumulative_y,
                "height": rendered_h,
                "zoom": eff_zoom,
                "page_w_pts": page_w_pts,
                "page_h_pts": page_h_pts,
                "content_left_pts": content_left_pts,  # for x-coordinate offsetting
            }
        )
        cumulative_y += rendered_h

        # Extract structured text dict for this page
        try:
            page_dict = page.get_text("dict")
        except Exception:
            page_dict = {"blocks": []}
        blocks = [b for b in page_dict.get("blocks", []) if b.get("type", 0) == 0]
        raw_blocks_per_page.append(blocks)
        # Aggregate flat text for narrative grounding
        try:
            full_text_parts.append(page.get_text())
        except Exception:
            pass

    doc.close()
    if not page_imgs:
        return None

    total_h = sum(im.height for im in page_imgs)
    canvas = Image.new("RGB", (width, total_h), "white")
    y = 0
    for im in page_imgs:
        canvas.paste(im, (0, y))
        y += im.height

    scroll_path = out_dir / "paper-scroll.png"
    scroll_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(scroll_path, format="PNG", optimize=True)
    log.info(
        "✅ PDF rendered: %s (%dx%d, %d pages)",
        scroll_path.name, width, total_h, len(page_imgs),
    )

    # ── Outline extraction ───────────────────────────────────────────────────
    anchors: list[dict] = []

    def _add_anchor(
        kind: str,
        page_idx: int,
        block: dict,
        text: str,
        label: str,
        anchor_id: str,
        height_blocks: list[dict] | None = None,
    ) -> None:
        rec = page_records[page_idx]
        x0, y0, x1, y1 = block["bbox"]
        # Optional: extend the bbox vertically to include trailing blocks
        # (used so abstract / section anchors capture the paragraph below them).
        if height_blocks:
            for nb in height_blocks:
                _, _, _, ny1 = nb["bbox"]
                y1 = max(y1, ny1)

        zoom = rec["zoom"]
        cl = rec.get("content_left_pts", 0.0)
        y_canvas = int(rec["y_offset"] + y0 * zoom)
        h_canvas = int(max(40, (y1 - y0) * zoom))
        x_canvas = int((x0 - cl) * zoom)
        w_canvas = int(max(40, (x1 - x0) * zoom))
        anchors.append(
            {
                "id": anchor_id,
                "label": label,
                "kind": kind,
                "page": page_idx + 1,
                "y": y_canvas,
                "h": h_canvas,
                "x": x_canvas,
                "w": w_canvas,
                "text": text[:400],
            }
        )

    # ── Pass 1: title (largest font block on page 0 with short text) ────────
    if raw_blocks_per_page:
        page0 = raw_blocks_per_page[0]
        candidates: list[tuple[float, dict]] = []
        for b in page0:
            t = _block_text(b)
            if 5 <= len(t) <= 200 and len(t.split()) <= 25:
                candidates.append((_block_max_font(b), b))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            best_size, best_block = candidates[0]
            t = _block_text(best_block)
            _add_anchor("title", 0, best_block, t, "Title", "title")

    # ── Pass 2: abstract (block following one whose text == "Abstract") ─────
    abstract_added = False
    for page_idx in range(min(2, len(raw_blocks_per_page))):
        blocks = raw_blocks_per_page[page_idx]
        for j, b in enumerate(blocks):
            t = _block_text(b)
            if not t:
                continue
            if t.strip().lower().rstrip(":.") == "abstract":
                # The next non-empty block is typically the abstract body
                for k in range(j + 1, min(j + 4, len(blocks))):
                    nb = blocks[k]
                    nt = _block_text(nb)
                    if len(nt) > 80:
                        # Optionally extend by 1-2 trailing blocks
                        _add_anchor(
                            "abstract", page_idx, nb, nt, "Abstract", "abstract",
                            height_blocks=[blocks[m] for m in range(k + 1, min(k + 3, len(blocks)))]
                            if k + 1 < len(blocks) else None,
                        )
                        abstract_added = True
                        break
                break
        if abstract_added:
            break

    # ── Pass 3: section headers ──────────────────────────────────────────────
    section_count = 0
    for page_idx, blocks in enumerate(raw_blocks_per_page):
        for j, b in enumerate(blocks):
            t = _block_text(b)
            if not t:
                continue
            if not _looks_like_section_header(t):
                continue
            t_low = t.lower().strip().rstrip(":.")
            if t_low == "abstract":
                continue
            # Capture the paragraph that follows the header for context
            body_text = ""
            extension: list[dict] = []
            for k in range(j + 1, min(j + 4, len(blocks))):
                nb = blocks[k]
                nt = _block_text(nb)
                if len(nt) > 60:
                    body_text = nt
                    extension.append(nb)
                    break

            label = t.strip()
            anchor_id = "sec_" + re.sub(r"[^a-z0-9]+", "_", t_low).strip("_")[:40] or f"sec_{section_count}"
            section_count += 1
            display_text = label + (" — " + body_text if body_text else "")
            _add_anchor(
                "section", page_idx, b, display_text, label, anchor_id,
                height_blocks=extension or None,
            )

    # ── Pass 4: figures and tables (caption blocks) ─────────────────────────
    fig_seen: set[str] = set()
    for page_idx, blocks in enumerate(raw_blocks_per_page):
        for b in blocks:
            t = _block_text(b)
            if not t:
                continue
            m = re.match(r"^(Figure|Fig\.?|Table)\s*(\d+)[:.\s]", t)
            if not m:
                continue
            kind = "figure" if m.group(1).lower().startswith("fig") else "table"
            num = m.group(2)
            key = f"{kind}_{num}"
            if key in fig_seen:
                continue
            fig_seen.add(key)
            label = f"{kind.capitalize()} {num}"
            _add_anchor(kind, page_idx, b, t, label, key)

    # Sort anchors by Y so the LLM can reason top-to-bottom
    anchors.sort(key=lambda a: a["y"])

    # Cap to max_anchors, but always keep title + abstract + every figure/table
    if len(anchors) > max_anchors:
        priority = [a for a in anchors if a["kind"] in {"title", "abstract", "figure", "table"}]
        sections = [a for a in anchors if a["kind"] == "section"]
        # Keep figures/tables/title/abstract in full, fill remainder with sections
        keep = priority + sections[: max(0, max_anchors - len(priority))]
        keep.sort(key=lambda a: a["y"])
        anchors = keep

    full_text = "\n\n".join(t for t in full_text_parts if t).strip()

    log.info(
        "📄 Paper outline: %d anchor(s) — %s",
        len(anchors),
        ", ".join(f"{a['kind']}:{a['label'][:24]}" for a in anchors[:10])
        + ("…" if len(anchors) > 10 else ""),
    )

    return {
        "scroll_image_path": scroll_path,
        "image_width": width,
        "image_height": total_h,
        "full_text": full_text,
        "anchors": anchors,
        "pages": page_records,
    }


def find_phrase_bbox_in_canvas(
    pdf_path: Path,
    phrase: str,
    pages_meta: list[dict],
    page_range: tuple[int, int] | None = None,
) -> dict | None:
    """
    Search for `phrase` in the PDF and return its bbox in canvas coords
    (absolute Y in the rendered tall image): {x, y, w, h, page}.

    Returns the FIRST hit closest to the top. Optionally limit the search to
    `page_range = (start, end_exclusive)` (zero-indexed) to disambiguate
    phrases that appear multiple times.
    """
    if not _HAS_PYMUPDF or not pdf_path.exists() or not phrase.strip():
        return None
    try:
        doc = fitz.open(str(pdf_path))  # type: ignore
    except Exception:
        return None

    start, end = (page_range or (0, len(pages_meta)))
    start = max(0, start)
    end = min(len(pages_meta), end, len(doc))

    try:
        for page_idx in range(start, end):
            rec = pages_meta[page_idx]
            page = doc[page_idx]
            try:
                rects = page.search_for(phrase, quads=False)
            except Exception:
                continue
            if not rects:
                continue
            rect = min(rects, key=lambda r: r.y0)
            zoom = rec["zoom"]
            cl = rec.get("content_left_pts", 0.0)
            return {
                "x": int((rect.x0 - cl) * zoom),
                "y": int(rec["y_offset"] + rect.y0 * zoom),
                "w": int(max(40, (rect.x1 - rect.x0) * zoom)),
                "h": int(max(20, (rect.y1 - rect.y0) * zoom)),
                "page": page_idx + 1,
            }
    finally:
        doc.close()
    return None


def _is_github_repo(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) if the URL is a GitHub repo, else None."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2).rstrip(".git")
    if owner.lower() in {"settings", "topics", "marketplace", "trending"}:
        return None
    return owner, repo


def scrape_github_readme_images(owner: str, repo: str) -> list[str]:
    """Fetch a GitHub repo's README via the API and harvest <img>/markdown image URLs."""
    images: list[str] = []
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    try:
        resp = httpx.get(
            api_url,
            headers={"Accept": "application/vnd.github.raw", "User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        readme_text = resp.text
    except Exception as exc:
        log.debug("GitHub README fetch failed for %s/%s: %s", owner, repo, exc)
        return []

    # Markdown images: ![alt](url)
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", readme_text):
        images.append(m.group(1))
    # HTML <img src="...">
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)', readme_text, re.IGNORECASE):
        images.append(m.group(1))

    # Resolve relative paths to raw.githubusercontent
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/"
    out: list[str] = []
    for u in images:
        if u.startswith(("http://", "https://")):
            out.append(u)
        else:
            out.append(urljoin(raw_base, u.lstrip("./")))
    return out


def scrape_html_page_images(page_url: str) -> list[str]:
    """Fetch an HTML page and harvest og:image, twitter:image, and inline <img> srcs."""
    images: list[str] = []
    try:
        resp = httpx.get(
            page_url,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=15,
        )
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
            return []
        html = resp.text
    except Exception as exc:
        log.debug("HTML fetch failed for %s: %s", page_url, exc)
        return []

    # OpenGraph / Twitter
    for m in re.finditer(
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image)["\'][^>]*content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    ):
        images.append(m.group(1))
    # Reverse direction (content first, property second)
    for m in re.finditer(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image)["\']',
        html,
        re.IGNORECASE,
    ):
        images.append(m.group(1))
    # Inline <img>
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)', html, re.IGNORECASE):
        images.append(m.group(1))

    return images


def scrape_source_pages(topic: dict, existing_urls: set[str]) -> list[str]:
    """
    Walk topic['sources'] and harvest additional image URLs from each page.

    Returns a deduplicated list of new image URLs not already present in
    `existing_urls`. Capped at _MAX_SCRAPED_IMAGES to avoid runaway sets.
    """
    discovered: list[str] = []
    seen: set[str] = set(existing_urls)

    sources = topic.get("sources") or []
    for src in sources:
        page_url = src.get("url")
        if not page_url:
            continue

        gh = _is_github_repo(page_url)
        if gh:
            owner, repo = gh
            log.info("Scraping GitHub README: %s/%s", owner, repo)
            raw_imgs = scrape_github_readme_images(owner, repo)
        else:
            log.info("Scraping page: %s", page_url[:80])
            raw_imgs = scrape_html_page_images(page_url)

        for u in raw_imgs:
            normalised = _normalise_image_url(u, page_url)
            if not normalised:
                continue
            if normalised in seen:
                continue
            if _is_badge_url(normalised):
                continue
            if normalised.lower().endswith(".svg"):
                continue
            seen.add(normalised)
            discovered.append(normalised)
            if len(discovered) >= _MAX_SCRAPED_IMAGES:
                return discovered

    return discovered


# ─── Full media pipeline ──────────────────────────────────────────────────────

class MediaResult:
    """Holds all processed media for a topic."""

    def __init__(self):
        # image_urls[url] = local Path (or None if unusable)
        self.image_map: dict[str, Path | None] = {}
        # video_urls[url] = {"thumbnail": Path, "clip": Path | None, "duration_sec": float | None}
        self.video_map: dict[str, dict] = {}
        # beat_id → local media Path (populated after narrative generation)
        self.beat_media: dict[int, Path | None] = {}
        # beat_id → list of additional media Paths (montage beats only — legacy)
        self.beat_extra_media: dict[int, list[Path]] = {}
        # beat_id → Pexels stock asset (photo OR video) chosen via pexels_query.
        # Always populated when a beat has a non-empty pexels_query, even if the
        # beat ALSO has a relevant local screenshot. The scene_writer can decide
        # to use it as primary content OR as a blurred ambient back layer.
        self.beat_pexels: dict[int, Path | None] = {}
        # beat_id → indicator of whether beat_pexels is a video file.
        self.beat_pexels_is_video: dict[int, bool] = {}
        # Optional: full-paper rendered as one tall image (for paper_walkthrough scenes).
        self.paper_scroll: Path | None = None
        # Optional: structured paper outline returned by process_paper_pdf().
        # Keys: image_width, image_height, anchors[], pages[], full_text
        self.paper_outline: dict | None = None
        # Path to the original downloaded PDF, retained so the scene_writer
        # post-processor can resolve highlight phrases to bboxes.
        self.paper_pdf_path: Path | None = None

    def best_image(self) -> Path | None:
        """Return the first usable downloaded image."""
        for path in self.image_map.values():
            if path is not None:
                return path
        return None


def process_media(
    topic: dict,
    out_dir: Path,
    openai_api_key: str,
    max_video_sec: int = 600,
) -> MediaResult:
    """
    Download and inspect all media from topic.json.
    Does NOT download video clips yet — that happens after narrative generation
    when we know which videos are actually needed.

    Returns a MediaResult with image_map and video_map populated.
    """
    result = MediaResult()
    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    raw_images: list[str] = list(topic.get("media", {}).get("images", []))
    raw_videos: list[str] = topic.get("media", {}).get("videos", [])

    # ── Process the topic's listed images ────────────────────────────────────
    log.info("Processing %d image(s) from topic.json...", len(raw_images))
    for i, url in enumerate(raw_images):
        dest = media_dir / f"img-{i:02d}{Path(urlparse(url).path).suffix or '.jpg'}"
        ok = check_and_download_image(url, dest)
        result.image_map[url] = dest if ok else None

    # ── Source-page scraping: pull more images from the actual article/repo ──
    # Always scrape — even if topic has many images — because source pages
    # often have far richer visuals (README screenshots, article inline images,
    # diagrams) than the limited set saved by the sourcing agent.
    scraped_urls = scrape_source_pages(topic, existing_urls=set(result.image_map.keys()))
    if scraped_urls:
        log.info("Found %d additional image(s) from source pages", len(scraped_urls))
        offset = len(raw_images)
        for j, url in enumerate(scraped_urls):
            dest = media_dir / f"img-{offset + j:02d}{Path(urlparse(url).path).suffix or '.jpg'}"
            ok = check_and_download_image(url, dest)
            result.image_map[url] = dest if ok else None

    # ── arXiv: download PDF, extract figures, render full paper for scroll ──
    arxiv_id: str | None = None
    for src in topic.get("sources") or []:
        candidate = _is_arxiv(src.get("url", ""))
        if candidate:
            arxiv_id = candidate
            break
    if arxiv_id and _HAS_PYMUPDF:
        log.info("arXiv paper detected: %s — fetching PDF", arxiv_id)
        # Stash the PDF outside media_dir so it's not picked up by the
        # data-URI embedding pass. We still need it later for phrase search.
        pdf_dir = out_dir / "_paper"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / f"arxiv-{arxiv_id}.pdf"
        if fetch_arxiv_pdf(arxiv_id, pdf_path):
            extracted = extract_pdf_figures(pdf_path, media_dir)
            for p in extracted:
                synthetic_url = f"pdf://{arxiv_id}/{p.name}"
                result.image_map[synthetic_url] = p
            # Render full paper + extract structured outline for walkthrough
            outline = process_paper_pdf(pdf_path, media_dir)
            if outline:
                result.paper_scroll = outline["scroll_image_path"]
                result.paper_outline = outline
                result.paper_pdf_path = pdf_path
        else:
            log.info("arXiv PDF download failed — skipping figure extraction")
    elif arxiv_id and not _HAS_PYMUPDF:
        log.info("arXiv paper detected but pymupdf not installed — skipping PDF extraction")

    # ── Process videos — metadata + thumbnail only at this stage ─────────────
    log.info("Processing %d video(s)...", len(raw_videos))
    for i, url in enumerate(raw_videos):
        thumb_dest = media_dir / f"video-thumb-{i:02d}.jpg"

        entry: dict = {
            "url": url,
            "thumbnail": None,
            "clip": None,
            "duration_sec": None,
            "title": None,
            "downloadable": False,   # will be set True if duration < max_video_sec
        }

        # Try to get YouTube thumbnail fast (no yt-dlp needed)
        if "youtube.com" in url or "youtu.be" in url:
            if get_youtube_thumbnail(url, thumb_dest):
                entry["thumbnail"] = thumb_dest

        # Get full metadata (duration, title) — skip if too slow
        meta = get_video_metadata(url)
        if meta:
            entry["duration_sec"] = meta.get("duration")
            entry["title"] = meta.get("title")
            if entry["duration_sec"] and entry["duration_sec"] < max_video_sec:
                entry["downloadable"] = True
            log.info(
                "   Video: '%s'  %.0fs  downloadable=%s",
                entry["title"] or url[:60],
                entry["duration_sec"] or 0,
                entry["downloadable"],
            )

        # Direct-MP4 fallback: if the URL looks like a static .mp4/.webm/.mov on
        # a regular CDN (Netlify, S3, blog asset), yt-dlp may fail to extract
        # duration. We mark it as downloadable so execute_beat_media will fetch
        # it via httpx, and we'll discover the real duration after download.
        if not entry["downloadable"]:
            lowered = url.split("?")[0].lower()
            if any(lowered.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v")):
                entry["downloadable"] = True
                entry["direct_download"] = True
                log.info("   Direct video URL detected: %s", url[:80])

        result.video_map[url] = entry

    usable_images = sum(1 for v in result.image_map.values() if v)
    usable_thumbs = sum(1 for v in result.video_map.values() if v.get("thumbnail"))
    log.info(
        "Media inventory: %d usable images, %d video thumbnails",
        usable_images,
        usable_thumbs,
    )
    return result


def execute_beat_media(
    beats: list[dict],
    media_result: MediaResult,
    out_dir: Path,
    openai_api_key: str,
    max_video_sec: int = 600,
) -> MediaResult:
    """
    After narrative generation, execute the media plan.

    Resolution chain per beat (SOURCE-MEDIA-FIRST policy):
      1. preferred_media_url → already-downloaded local image / thumbnail
      2. needs_video_clip    → demo clip download
      3. needs_generated_image → GPT-image-1 (if quota allows)
      4. inventory-leftover fallback → rotate UNUSED source assets into
         beats that haven't pinned media yet (NEW)
      5. pexels_query        → Pexels stock photo or video
      6. fal.ai FLUX schnell → AI-generated photoreal still
      7. fallback to MediaResult.best_image() (last resort)

    Source media wins. Pexels and FAL only fire when the inventory is
    exhausted for a given beat. beat_pexels is still populated for every
    beat with a query so the scene-writer can use stock as a blurred
    ambient back layer behind text-only overlays.
    """
    # Lazy imports keep the module load cheap when these features are unused.
    from .pexels import search_photo, search_video  # type: ignore
    try:
        from .fal_image import generate_photoreal  # type: ignore
    except ImportError:  # pragma: no cover
        generate_photoreal = None  # type: ignore

    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    fal_key = os.getenv("FAL_KEY", "").strip()

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # ── Inventory-leftover fallback bookkeeping ──────────────────────────
    # Track which downloaded source assets have already been pinned by an
    # earlier beat. Beats that don't pin anything via the LLM-driven
    # preferred_media_url / video_url / generate_prompt path can then
    # claim an UNUSED source asset before we ever reach Pexels. This is
    # how we enforce "real source media over stock library" on the Python
    # side, in case the LLM still doesn't fully comply with the new prompt
    # rule.
    #
    # Skip URLs that are obvious junk for primary content (avatars,
    # logos, favicon-sized icons) — we still keep them in image_map for
    # context but don't auto-rotate them in as beat media.
    def _is_junk_source_url(url: str) -> bool:
        u = (url or "").lower()
        if any(tok in u for tok in ("avatar", "favicon", "logo", "icon-", "/icons/")):
            return True
        return False

    claimed_source_paths: set[Path] = set()

    # ── PHASE 1: LLM-driven assignments (steps 1-3) ──────────────────────
    # Run these for every beat first so we know which source assets are
    # actually claimed before any beat falls through to the inventory-
    # leftover / Pexels / FAL fallbacks.
    for beat in beats:
        bid = beat["id"]

        # 1 — Try to resolve preferred_media_url to an already-downloaded local file
        pref_url = beat.get("preferred_media_url")
        if pref_url:
            local = media_result.image_map.get(pref_url)
            # Safety net: the narrative LLM occasionally emits a truncated URL
            # (the original prompt used to truncate at 80 chars). Fall back to
            # a prefix / substring match against image_map so a near-miss
            # still resolves to a real Tier-A image instead of dropping to
            # Pexels stock.
            if (not local or not local.exists()) and isinstance(pref_url, str):
                pref_norm = pref_url.rstrip(" .,;)]'\"")
                for url, p in media_result.image_map.items():
                    if not p or not p.exists():
                        continue
                    if (
                        url == pref_norm
                        or url.startswith(pref_norm)
                        or pref_norm.startswith(url)
                    ):
                        log.info(
                            "Beat %d: preferred_media_url near-match — %r → %s",
                            bid, pref_norm[:60], p.name,
                        )
                        local = p
                        break
            if local and local.exists():
                media_result.beat_media[bid] = local
            else:
                vid_entry = media_result.video_map.get(pref_url, {})
                thumb = vid_entry.get("thumbnail")
                if thumb and Path(thumb).exists():
                    media_result.beat_media[bid] = Path(thumb)
        else:
            media_result.beat_media[bid] = None

        # 2 — Download video clip if Claude flagged it
        video_url = beat.get("video_url")
        if beat.get("needs_video_clip") and video_url:
            vid_entry = media_result.video_map.get(video_url, {})
            if vid_entry.get("downloadable"):
                clip_dest = media_dir / f"clip-beat{bid:02d}.mp4"
                if not clip_dest.exists():
                    log.info("Downloading clip for beat %d: %s", bid, video_url[:60])
                    ok = download_video_clip(video_url, clip_dest, max_sec=90)
                    if ok:
                        vid_entry["clip"] = clip_dest
                        media_result.beat_media[bid] = clip_dest
                else:
                    media_result.beat_media[bid] = clip_dest
            else:
                thumb = vid_entry.get("thumbnail")
                if thumb:
                    media_result.beat_media[bid] = Path(thumb)
                    log.info(
                        "Beat %d: video too long / not downloadable → using thumbnail", bid
                    )

        # 3 — Generate image if needed (and no media resolved yet)
        if beat.get("needs_generated_image") and beat.get("generate_prompt"):
            gen_dest = media_dir / f"gen-beat{bid:02d}.png"
            if not gen_dest.exists():
                log.info("Generating image for beat %d...", bid)
                ok = generate_image(beat["generate_prompt"], gen_dest, openai_api_key)
                if ok:
                    media_result.beat_media[bid] = gen_dest
            else:
                media_result.beat_media[bid] = gen_dest

    # Snapshot every source asset claimed by Phase 1 so Phase 2 knows
    # which inventory items are still free to rotate into unmedia'd beats.
    for cur in media_result.beat_media.values():
        if cur is not None:
            claimed_source_paths.add(cur)

    # ── PHASE 2: fallbacks (steps 4-7) for beats still without media ─────
    for beat in beats:
        bid = beat["id"]

        # 4 — Inventory-leftover fallback. If the beat is unmedia'd and we
        # have unclaimed source-inventory images, rotate one in. This
        # beats Pexels because a real article asset is on-brand even if
        # the LLM forgot to pin it. We honor explicit
        # needs_generated_image: if it asked for a generation and that
        # generation failed (401, quota, etc.), DON'T silently swap in a
        # random inventory image — let it fall through to FAL.
        if (
            not media_result.beat_media.get(bid)
            and not beat.get("needs_generated_image")
        ):
            for url, p in media_result.image_map.items():
                if not p or not p.exists() or p in claimed_source_paths:
                    continue
                if _is_junk_source_url(url):
                    continue
                media_result.beat_media[bid] = p
                claimed_source_paths.add(p)
                log.info(
                    "Beat %d: inventory-leftover fallback → %s (no LLM "
                    "preferred_media_url, claiming unused source asset)",
                    bid, p.name,
                )
                break

        # 5 — Pexels stock. Always download when we have a query so the
        # scene-writer has stock available as an ambient back-layer for
        # text-only overlays — but ONLY promote to primary beat_media if
        # neither the LLM-driven path nor the inventory-leftover pass
        # already landed something.
        pexels_query = (beat.get("pexels_query") or "").strip()
        stock_kind = (beat.get("stock_kind") or "video").lower()
        if pexels_query and pexels_key:
            try:
                if stock_kind == "photo":
                    p_path = search_photo(pexels_query, pexels_key, media_dir)
                    is_video = False
                else:
                    p_path = search_video(pexels_query, pexels_key, media_dir)
                    is_video = bool(p_path)
                    if not p_path:
                        # Video search empty → try photo so we still get something
                        p_path = search_photo(pexels_query, pexels_key, media_dir)
                        is_video = False
                if p_path and p_path.exists():
                    media_result.beat_pexels[bid] = p_path
                    media_result.beat_pexels_is_video[bid] = is_video
                    # Promote Pexels to primary content ONLY if nothing
                    # else (source pin, generated image, or
                    # inventory-leftover) landed for this beat.
                    if not media_result.beat_media.get(bid):
                        media_result.beat_media[bid] = p_path
            except Exception as exc:  # don't fail the run on stock-fetch hiccups
                log.warning("Pexels lookup failed for beat %d (%r): %s", bid, pexels_query, exc)

        # 6 — fal.ai FLUX as last-resort image generator (only if still nothing
        # AND the beat has a generate_prompt OR a pexels_query to seed FLUX with).
        if not media_result.beat_media.get(bid) and generate_photoreal and fal_key:
            seed_prompt = (
                beat.get("generate_prompt")
                or pexels_query
                or beat.get("text", "")[:80]
            )
            if seed_prompt:
                fal_path = generate_photoreal(seed_prompt, media_dir, api_key=fal_key)
                if fal_path:
                    media_result.beat_media[bid] = fal_path

        # 7 — Final fallback: any usable downloaded image.
        if not media_result.beat_media.get(bid):
            fallback = media_result.best_image()
            if fallback:
                log.debug("Beat %d: using fallback image %s", bid, fallback.name)
                media_result.beat_media[bid] = fallback

    return media_result


def build_media_inventory_text(media_result: MediaResult) -> str:
    """Return a human-readable text block for the Claude narrative prompt."""
    lines = ["AVAILABLE MEDIA:"]
    lines.append("\nImages (usable):")
    lines.append(
        "  ⚠️ COPY URLs VERBATIM into preferred_media_url — including any"
        " query string, file extension, and trailing punctuation. Truncated"
        " URLs cannot be matched and will silently fall back to stock photos."
    )
    for url, path in media_result.image_map.items():
        status = f"✅ {path.name}" if path else "❌ unusable"
        lines.append(f"  {url}  →  {status}")

    lines.append("\nVideos:")
    for url, info in media_result.video_map.items():
        dur = f"{info['duration_sec']:.0f}s" if info.get("duration_sec") else "unknown"
        title = info.get("title") or ""
        thumb = "✅ thumbnail" if info.get("thumbnail") else "❌ no thumbnail"
        dl = "✅ downloadable" if info.get("downloadable") else "❌ too long"
        lines.append(f"  {url}")
        lines.append(f"    title={title[:60]}  duration={dur}  {thumb}  {dl}")

    # ── Paper outline (research-paper topics) ───────────────────────────────
    if media_result.paper_outline:
        outline = media_result.paper_outline
        anchors = outline.get("anchors", [])
        full_text = outline.get("full_text", "") or ""
        if anchors:
            lines.append("")
            lines.append(
                "📄 RESEARCH PAPER DETECTED — this is a paper-walkthrough topic."
            )
            lines.append(
                "Plan the script as an EXPLANATION of the paper. Cover (in order):"
                " what problem → key idea → method/figure → result/table → why it matters."
            )
            lines.append("")
            lines.append("PAPER ANCHORS (each can be a stop in the paper_walkthrough scene):")
            for a in anchors:
                snippet = (a.get("text") or "").replace("\n", " ")[:160]
                lines.append(
                    f"  • [{a['id']}] ({a['kind']}) {a['label']} — {snippet}"
                )
        if full_text:
            preview = full_text.replace("\n", " ").strip()
            # Cap to a few thousand chars to keep prompt size sane
            if len(preview) > 6000:
                preview = preview[:6000] + " …(paper truncated)"
            lines.append("")
            lines.append("PAPER FULL TEXT (read this end-to-end before writing the narrative):")
            lines.append(preview)

    return "\n".join(lines)
