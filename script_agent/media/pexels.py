# ─── pexels.py ───────────────────────────────────────────────────────────────
# Thin Pexels client used by the script_agent media resolver.
#
# Why this file exists:
#   When a beat has no relevant downloaded screenshot, we want to fill the
#   slot with stock footage instead of a flat black background or floating-
#   card salad. Pexels has free 9:16 vertical b-roll and a generous free
#   tier (200 req/hr, 20K req/month) so it's the cheapest way to get
#   "real-looking" motion behind narration.
#
# Design choices:
#   • Photos AND videos. Photos are used as still backgrounds (blurred);
#     videos are used as ambient back layers behind text-only scenes.
#   • We always ask for portrait orientation — the renderer is 9:16.
#   • We download the asset to disk once and cache by query+kind so the
#     same beat doesn't re-fetch on a re-render.

import hashlib
import logging
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com"
USER_AGENT = "PinchContentGen/1.0"


def _cache_key(query: str, kind: str) -> str:
    return hashlib.sha1(f"{kind}:{query.lower().strip()}".encode()).hexdigest()[:16]


def _has_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip())


# ─── Photo search ────────────────────────────────────────────────────────────


def search_photo(
    query: str,
    api_key: str,
    out_dir: Path,
    *,
    orientation: str = "portrait",
    timeout: float = 12.0,
    exclude_paths: Optional[set[Path]] = None,
) -> Optional[Path]:
    """
    Search Pexels for the best portrait photo matching `query` and download
    it under `out_dir/pexels-photo-<hash>.jpg`. Returns the local Path on
    success, None if no result or any error.

    `exclude_paths` lets the caller pass a registry of already-used Pexels
    files; the function skips any candidate that would dedupe against
    them. Used by the reel-level dedupe in scene_writer.py.
    """
    if not _has_key(api_key):
        return None
    if not query or not query.strip():
        return None

    excluded = exclude_paths or set()

    cache_name = f"pexels-photo-{_cache_key(query, 'photo')}.jpg"
    dest = out_dir / cache_name
    if dest.exists() and dest.stat().st_size > 1024 and dest not in excluded:
        return dest

    headers = {"Authorization": api_key.strip(), "User-Agent": USER_AGENT}
    params = {
        "query": query,
        "per_page": 8,
        "orientation": orientation,
    }
    try:
        r = httpx.get(f"{PEXELS_API}/v1/search", headers=headers, params=params, timeout=timeout)
        if r.status_code != 200:
            log.debug("Pexels photo search HTTP %s for %r", r.status_code, query)
            return None
        data = r.json()
        photos = data.get("photos") or []
        if not photos:
            log.debug("Pexels: no photos for %r", query)
            return None
    except Exception as exc:
        log.debug("Pexels photo search failed for %r: %s", query, exc)
        return None

    # Walk results in order; skip any whose download path is already used.
    portrait_first = sorted(
        photos,
        key=lambda p: 0 if (p.get("height") or 0) >= (p.get("width") or 0) else 1,
    )
    for chosen in portrait_first:
        src = chosen.get("src") or {}
        img_url = src.get("large2x") or src.get("large") or src.get("original")
        if not img_url:
            continue
        # Per-photo cache key based on the URL so consecutive calls with
        # the same query but different excluded sets land on different
        # files instead of overwriting each other.
        per_dest = out_dir / f"pexels-photo-{_cache_key(img_url, 'photo-url')}.jpg"
        if per_dest in excluded:
            continue
        if per_dest.exists() and per_dest.stat().st_size > 1024:
            return per_dest
        try:
            img_resp = httpx.get(img_url, timeout=timeout)
            img_resp.raise_for_status()
            out_dir.mkdir(parents=True, exist_ok=True)
            per_dest.write_bytes(img_resp.content)
            log.info(
                "Pexels photo: %r → %s (%dx%d)",
                query,
                per_dest.name,
                chosen.get("width", 0),
                chosen.get("height", 0),
            )
            return per_dest
        except Exception as exc:
            log.debug("Pexels photo download failed: %s", exc)
            continue
    return None


# ─── Video search ────────────────────────────────────────────────────────────


def search_video(
    query: str,
    api_key: str,
    out_dir: Path,
    *,
    orientation: str = "portrait",
    min_height: int = 720,
    max_duration_sec: int = 30,
    timeout: float = 20.0,
    exclude_paths: Optional[set[Path]] = None,
) -> Optional[Path]:
    """
    Search Pexels for the best portrait video matching `query` and download
    its highest-quality MP4 under `out_dir/pexels-video-<hash>.mp4`.

    Filters:
      • Orientation: portrait (the renderer is 9:16).
      • Minimum height: 720px so we can letterbox without it looking pixelated.
      • Maximum duration: 30s — anything longer is wasteful for ambient bg use.
    """
    if not _has_key(api_key):
        return None
    if not query or not query.strip():
        return None

    excluded = exclude_paths or set()

    headers = {"Authorization": api_key.strip(), "User-Agent": USER_AGENT}
    params = {
        "query": query,
        "per_page": 12,
        "orientation": orientation,
        "size": "medium",
    }
    try:
        r = httpx.get(
            f"{PEXELS_API}/videos/search", headers=headers, params=params, timeout=timeout
        )
        if r.status_code != 200:
            log.debug("Pexels video search HTTP %s for %r", r.status_code, query)
            return None
        data = r.json()
        videos = data.get("videos") or []
        if not videos:
            log.debug("Pexels: no videos for %r", query)
            return None
    except Exception as exc:
        log.debug("Pexels video search failed for %r: %s", query, exc)
        return None

    # Filter to videos within the duration cap, keep API order.
    candidates = [
        v for v in videos
        if 0 < (v.get("duration") or 0) <= max_duration_sec
    ] or videos[:]

    # Walk candidates in order; the first one whose download path isn't
    # already in `excluded` wins. This is what enforces the
    # one-Pexels-clip-per-reel rule when callers pass the registry.
    def _score(f: dict) -> int:
        w = f.get("width") or 0
        h = f.get("height") or 0
        if h < min_height:
            return -10000
        return -(abs(h - 1920) + abs(w - 1080))

    for chosen in candidates:
        files = chosen.get("video_files") or []
        files_sorted = sorted(
            [f for f in files if (f.get("link") or "").endswith((".mp4", ".webm", ".mov"))],
            key=_score,
            reverse=True,
        )
        if not files_sorted:
            continue
        best = files_sorted[0]
        link = best.get("link")
        if not link:
            continue
        # Use the file URL as the dedupe key so different videos under
        # the same query land on different files.
        per_dest = out_dir / f"pexels-video-{_cache_key(link, 'video-url')}.mp4"
        if per_dest in excluded:
            continue
        if per_dest.exists() and per_dest.stat().st_size > 1024:
            return per_dest
        try:
            with httpx.stream("GET", link, timeout=timeout) as resp:
                resp.raise_for_status()
                out_dir.mkdir(parents=True, exist_ok=True)
                with open(per_dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
            log.info(
                "Pexels video: %r → %s (%dx%d, %ds)",
                query,
                per_dest.name,
                best.get("width", 0),
                best.get("height", 0),
                chosen.get("duration", 0),
            )
            return per_dest
        except Exception as exc:
            log.debug("Pexels video download failed: %s", exc)
            if per_dest.exists():
                try:
                    per_dest.unlink()
                except OSError:
                    pass
            continue
    return None


# ─── Convenience: best-effort still ──────────────────────────────────────────


def search_best_still(
    query: str,
    api_key: str,
    out_dir: Path,
    timeout: float = 12.0,
) -> Optional[Path]:
    """
    Try a portrait photo first; fall back to grabbing a frame from a portrait
    video if no photo is available. Returns local Path or None.
    """
    p = search_photo(query, api_key, out_dir, timeout=timeout)
    if p is not None:
        return p
    # If no photo, try video — caller can letterbox it as a still.
    return search_video(query, api_key, out_dir, timeout=timeout)
