# ─── fal_image.py ────────────────────────────────────────────────────────────
# Thin fal.ai client used as the LAST-RESORT image source.
#
# Sourcing chain in script_agent:
#   1. Local screenshots already downloaded in topic.json
#   2. Pexels stock (portrait photo or 9:16 video)  ← cheap, fast
#   3. fal.ai FLUX schnell                          ← only when 1+2 fail
#
# We use FLUX schnell (~4 inference steps, ~$0.025/image) and ask for a
# portrait crop. Output is downloaded to disk and cached by prompt hash.
#
# This module gracefully degrades:
#   • If `fal_client` isn't installed → returns None (logs once).
#   • If FAL_KEY is empty → returns None silently.

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

try:  # pragma: no cover
    import fal_client  # type: ignore
    _HAS_FAL = True
except ImportError:
    fal_client = None  # type: ignore
    _HAS_FAL = False


_WARNED_NO_LIB = False


def _cache_key(prompt: str) -> str:
    return hashlib.sha1(prompt.lower().strip().encode()).hexdigest()[:16]


def _ensure_lib_warning() -> None:
    global _WARNED_NO_LIB
    if not _WARNED_NO_LIB:
        log.warning(
            "fal-client not installed; FLUX fallback disabled. "
            "Run `pip install fal-client` to enable."
        )
        _WARNED_NO_LIB = True


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_photoreal(
    prompt: str,
    out_dir: Path,
    *,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> Optional[Path]:
    """
    Generate a photorealistic portrait image with FLUX schnell.

    The prompt is automatically wrapped with photo-style modifiers ("press
    photo, DSLR, natural lighting, 35mm") to fight the default fal.ai look,
    which tends towards illustrated / overly stylized.
    """
    api_key = api_key or os.getenv("FAL_KEY") or ""
    if not api_key.strip():
        return None
    if not _HAS_FAL:
        _ensure_lib_warning()
        return None
    if not prompt or not prompt.strip():
        return None

    cache_name = f"fal-flux-{_cache_key(prompt)}.png"
    dest = out_dir / cache_name
    if dest.exists() and dest.stat().st_size > 1024:
        return dest

    # Photoreal wrapper — keeps the user prompt centered while nudging FLUX
    # toward "press photo" rather than illustration.
    wrapped = (
        f"{prompt.strip()}, photorealistic, DSLR press photo, 35mm, "
        "natural lighting, sharp focus, editorial photography"
    )

    os.environ["FAL_KEY"] = api_key.strip()
    try:
        result = fal_client.run(  # type: ignore[union-attr]
            "fal-ai/flux/schnell",
            arguments={
                "prompt": wrapped,
                "image_size": "portrait_16_9",
                "num_inference_steps": 4,
                "num_images": 1,
                "enable_safety_checker": True,
            },
        )
    except Exception as exc:
        log.warning("fal.ai FLUX call failed: %s", exc)
        return None

    images = (result or {}).get("images") or []
    if not images:
        log.warning("fal.ai FLUX returned no images for prompt: %s", prompt[:80])
        return None
    img_url = images[0].get("url")
    if not img_url:
        return None

    try:
        r = httpx.get(img_url, timeout=timeout)
        r.raise_for_status()
        out_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        log.info("fal.ai FLUX: %s → %s", prompt[:60], dest.name)
        return dest
    except Exception as exc:
        log.warning("fal.ai image download failed: %s", exc)
        return None
