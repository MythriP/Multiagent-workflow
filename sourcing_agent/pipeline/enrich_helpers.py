"""
enrich_helpers.py — small, focused utilities used by enrich.py:

  • `score_outbound_link`  — decide whether an `<a href>` inside an article
                             body is worth following as a fresh source
  • `validate_image`       — fetch an image's actual decoded dimensions and
                             reject anything that's logo/badge/avatar sized
  • `probe_video_duration` — best-effort duration probe via yt-dlp metadata
                             or ffprobe HEAD-stream, used to decide whether
                             a video is short, long, or out of scope

These are intentionally side-effect-free (no global state, no logging
config) so they compose cleanly with `enrich.enrich_cluster`.
"""

from __future__ import annotations

import io
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# ── Outbound link relevance ──────────────────────────────────────────────────

# Domains that are pure noise: ad networks, share buttons, analytics,
# social-network share endpoints, CDNs that don't host article content.
_NOISE_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "linkedin.com", "reddit.com",
    "pinterest.com", "tumblr.com", "instagram.com", "tiktok.com",
    "youtube.com/share", "wa.me", "t.me",
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "googlesyndication.com", "googleadservices.com", "adservice.google.com",
    "amazon-adsystem.com", "rubiconproject.com", "criteo.com",
    "scorecardresearch.com", "nr-data.net", "newrelic.com",
    "segment.io", "segment.com", "branch.io",
    "fonts.googleapis.com", "fonts.gstatic.com", "gstatic.com",
    "platform.theverge.com",  # The Verge's own asset CDN — we already have
                              # the parent article; CDN hits are not new sources
}

# Path tokens that signal "this is real content, follow it"
_GOOD_URL_TOKENS = (
    "/blog/", "/research/", "/paper/", "/papers/", "/reports/", "/report/",
    "/study/", "/news/", "/article/", "/posts/", "/post/", "/release/",
    "/announcements/", "/press/", "/insights/", "/notes/", "/case/",
)

# Anchor-text hints that the link is the article's primary source
_GOOD_ANCHOR_HINTS = re.compile(
    r"\b("
    r"report|research|paper|study|blog post|writeup|write-up|"
    r"announce(?:d|ment)?|publish(?:ed|ing)?|release(?:d)?|reveal(?:ed)?|"
    r"shared|disclosed|find(?:ing|ings)?|according to|"
    r"full report|full paper|read more|read the|see the|"
    r"detail(?:ed|s)?|methodology|technical (?:report|details?)"
    r")\b",
    re.IGNORECASE,
)

# Anchor text or URL paths that are clearly site-chrome links (legal, account,
# subscribe). They sometimes match cross-domain (e.g. consent management on a
# CDN), so we have to reject them explicitly.
_BAD_ANCHOR_HINTS = re.compile(
    r"\b("
    r"privacy(?:\s+(?:notice|policy))?|terms(?:\s+of\s+(?:service|use))?|"
    r"cookie\s+policy|cookie\s+settings|do\s+not\s+sell|consent|"
    r"sign\s+in|log\s+in|sign\s+up|register|create\s+account|"
    r"subscribe|newsletter|unsubscribe|"
    r"contact(?:\s+us)?|about(?:\s+us)?|advertise|sponsorship|"
    r"editorial\s+(?:standards|policy)|ethics\s+statement|"
    r"accessibility|sitemap|RSS\s+feed"
    r")\b",
    re.IGNORECASE,
)
_BAD_URL_TOKENS = (
    "/privacy", "/terms", "/cookie", "/legal/", "/about/",
    "/contact", "/subscribe", "/newsletter", "/unsubscribe",
    "/login", "/signin", "/signup", "/register",
    "/sitemap", "/accessibility", "/advertise", "/careers",
    "/dmca", "/feedback", "/help", "/support", "/faq",
)

# File extensions we never follow as an article (we *do* track them as
# documents/media when relevant — that's handled separately)
_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".tgz", ".gz", ".7z",
    ".mp3", ".wav", ".m4a", ".ogg",
    ".mp4", ".mov", ".webm", ".m4v",  # videos handled by media extractor
)


def _domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def is_noise_domain(url: str) -> bool:
    d = _domain(url)
    if not d:
        return True
    for noise in _NOISE_DOMAINS:
        if d == noise or d.endswith("." + noise) or noise in url:
            return True
    return False


def score_outbound_link(href: str, anchor_text: str, source_url: str) -> int:
    """
    Score an outbound `<a>` link. Higher is better. Negative scores mean
    "definitely don't follow." A score of ≥ 2 is the typical follow threshold.
    """
    if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
        return -10

    # Normalise relative URLs we can't fully resolve
    if not href.startswith(("http://", "https://")):
        return -10

    if any(href.lower().split("?")[0].endswith(ext) for ext in _SKIP_EXTENSIONS):
        return -10

    if is_noise_domain(href):
        return -10

    href_lower = href.lower()
    if any(tok in href_lower for tok in _BAD_URL_TOKENS):
        return -10
    if anchor_text and _BAD_ANCHOR_HINTS.search(anchor_text):
        return -10

    src_dom = _domain(source_url)
    href_dom = _domain(href)

    score = 0

    # Cross-domain bump — primary sources are usually elsewhere
    if href_dom and href_dom != src_dom:
        score += 2
    else:
        # Same-domain links are mostly internal navigation; rarely the primary
        # source. Drop hard.
        score -= 2

    if any(tok in href.lower() for tok in _GOOD_URL_TOKENS):
        score += 1

    if anchor_text and len(anchor_text.strip()) >= 4:
        cleaned = anchor_text.strip()
        # Pure "click here" / "read more" links are weak unless URL is great
        if _GOOD_ANCHOR_HINTS.search(cleaned):
            score += 2
        # Anchor text that's a known org name boost
        if re.search(r"\b(?:research|labs|ai)\b", cleaned, re.IGNORECASE):
            score += 1

    # Penalise extremely long or query-heavy URLs (usually trackers)
    if "?utm_" in href or "ref=" in href or "fbclid=" in href:
        score -= 1

    return score


# ── Image quality validation ─────────────────────────────────────────────────


@dataclass
class ImageInfo:
    url: str
    width: int
    height: int
    bytes_read: int


def validate_image(
    client: httpx.Client,
    url: str,
    min_w: int = 200,
    min_h: int = 200,
    max_aspect: float = 6.0,
    max_bytes: int = 4 * 1024 * 1024,
) -> Optional[ImageInfo]:
    """
    Fetch (or partially fetch) an image and decide if it's a "real" content
    image. We need actual pixel dimensions because publisher HTML often omits
    width/height attributes — that's how site logos and licence badges sneak
    past the dimensional filters. Returns ImageInfo on pass, None on fail.

    The function is best-effort: it short-circuits on obvious junk URLs
    (data:, analytics endpoints) and on read errors.
    """
    if not url or url.startswith("data:"):
        return None
    if is_noise_domain(url):
        return None
    if not _HAS_PIL:
        # Fall through to "trust the URL" — keep it.
        return ImageInfo(url=url, width=min_w, height=min_h, bytes_read=0)

    try:
        # Stream up to `max_bytes` so we can decode dimensions without
        # downloading an arbitrarily large file.
        with client.stream("GET", url, timeout=8) as resp:
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("Content-Type", "")
            if ctype and not (ctype.startswith("image/") or "octet-stream" in ctype):
                return None
            buf = io.BytesIO()
            n = 0
            for chunk in resp.iter_bytes(8192):
                buf.write(chunk)
                n += len(chunk)
                if n >= max_bytes:
                    break
            buf.seek(0)
        try:
            with Image.open(buf) as pil:
                w, h = pil.size
        except Exception:
            return None
    except Exception:
        return None

    if w < min_w or h < min_h:
        return None
    if w / max(h, 1) > max_aspect or h / max(w, 1) > max_aspect:
        return None
    return ImageInfo(url=url, width=w, height=h, bytes_read=n)


# ── Video duration probing ───────────────────────────────────────────────────


@dataclass
class VideoInfo:
    url: str
    duration_sec: Optional[float]
    title: Optional[str]
    description: Optional[str]
    chapters: list[dict]


def _ytdlp_metadata(url: str, timeout: int = 20) -> Optional[dict]:
    """Run yt-dlp -J to extract metadata. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", "--no-playlist", "--no-warnings", url],
            capture_output=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None
        import json as _json
        return _json.loads(result.stdout.decode("utf-8", errors="ignore"))
    except Exception:
        return None


def probe_video(url: str) -> VideoInfo:
    """
    Best-effort duration / chapter probe.

    For YouTube/Vimeo: yt-dlp returns rich metadata (duration, chapters,
    auto-generated description). For raw .mp4/.webm: we'd need ffprobe over
    HTTP, which is too heavy here — we return duration=None and let the
    enrichment loop accept the clip optimistically (those direct-mp4 clips
    are typically very short anyway, e.g. blog GIFs and demo loops).
    """
    meta = _ytdlp_metadata(url) or {}
    chapters_raw = meta.get("chapters") or []
    chapters: list[dict] = []
    for ch in chapters_raw:
        if not isinstance(ch, dict):
            continue
        chapters.append({
            "title": (ch.get("title") or "").strip(),
            "start_time": float(ch.get("start_time") or 0),
            "end_time": float(ch.get("end_time") or 0) if ch.get("end_time") else None,
        })
    return VideoInfo(
        url=url,
        duration_sec=float(meta["duration"]) if meta.get("duration") else None,
        title=meta.get("title"),
        description=meta.get("description"),
        chapters=chapters,
    )


def pick_video_windows(
    info: VideoInfo,
    topic_keywords: list[str],
    max_windows: int = 3,
    default_window_sec: int = 30,
) -> list[dict]:
    """
    Choose 1–N windows inside a long video that look most relevant to the
    topic. Strategy:
      1. If chapters exist → score each chapter's title against topic keywords;
         take the top N.
      2. Else → fall back to evenly-spaced windows: start, middle, end.
    Returns a list of `{start_sec, end_sec, label}` dicts (always trimmed
    to the actual video duration).
    """
    if info.duration_sec is None:
        return []

    keywords = [k.lower() for k in topic_keywords if k]

    def _kw_score(text: str) -> int:
        text_l = text.lower()
        return sum(1 for k in keywords if k in text_l)

    windows: list[dict] = []

    if info.chapters:
        scored = []
        for ch in info.chapters:
            t = ch.get("title", "")
            score = _kw_score(t)
            if score <= 0:
                continue
            start = float(ch.get("start_time") or 0)
            end = float(ch.get("end_time") or 0) or min(
                start + default_window_sec, info.duration_sec
            )
            scored.append((score, start, end, t))
        scored.sort(key=lambda x: -x[0])
        for _, start, end, label in scored[:max_windows]:
            windows.append({
                "start_sec": round(start, 1),
                "end_sec": round(min(end, info.duration_sec), 1),
                "label": label,
            })

    if not windows:
        # Fallback: no chapters or no chapter matched → sample evenly
        d = info.duration_sec
        anchors = [d * 0.10, d * 0.50, d * 0.85][:max_windows]
        for i, a in enumerate(anchors):
            start = max(0, a - default_window_sec / 2)
            end = min(d, a + default_window_sec / 2)
            windows.append({
                "start_sec": round(start, 1),
                "end_sec": round(end, 1),
                "label": f"sample window {i + 1}",
            })

    return windows
