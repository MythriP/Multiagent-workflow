# ─── lipsync.py ───────────────────────────────────────────────────────────────
# Talking-avatar pipeline (Phase C — Option B).
#
# Phase C lipsync change: we no longer composite the avatar onto a magenta
# chromakey plate or post-process to a VP9-with-alpha WebM. Instead the
# avatar segments play the FULL ORIGINAL avatar-source.png (background
# included — the Spain-street setting) as the talking-head subject, and
# the model's mp4 output is rendered full-canvas in the corresponding
# avatar_full / hook scenes. This drops a brittle filter chain and gives
# the host a real environment instead of a transparent bust floating
# over scene content.
#
# What this module produces now:
#   • One mp4 PER avatar segment (contiguous run of host_avatar=true
#     scenes), trimmed to the segment's exact audio window.
#   • A `lipsync_segments` list returned to the caller — render.py
#     attaches each clip to the scene(s) it covers via OffthreadVideo.
#
# Audio chunking: most photo→talking models cap input audio at ~30s per
# call, so segments longer than ~28s get split, generated in parallel,
# and concatenated. Cache key is sha1(audio_chunk + image + model) so
# identical re-renders cost $0 on repeat. Cache hits print
# "lipsync cache HIT: <key>" to stdout.
#
# Cost model (defaults, fal-ai/bytedance/omnihuman, $0.14 per audio sec):
#   ~10s of avatar = ~$1.40 per fresh render, $0.00 on repeat.

import hashlib
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_CACHE_ROOT = Path(__file__).parent / ".cache" / "lipsync"

# Canonical canvas params used inside fal.ai inputs and intermediate
# encodes. Outputs are 720×1280 portrait so they cover the 9:16 reel.
_NORM_W = 720
_NORM_H = 1280
_NORM_FPS = 25

# fal.ai image-to-talking-video models we know about and their schemas.
_MODEL_SCHEMAS: dict[str, dict] = {
    "fal-ai/bytedance/omnihuman": {
        "image_arg": "image_url", "audio_arg": "audio_url",
        "max_audio_sec": 30.0, "extras": {},
    },
    "fal-ai/bytedance/omnihuman/v1.5": {
        "image_arg": "image_url", "audio_arg": "audio_url",
        "max_audio_sec": 30.0, "extras": {},
    },
    "fal-ai/echomimic-v3": {
        "image_arg": "image_url", "audio_arg": "audio_url",
        "max_audio_sec": 30.0,
        "extras": {
            "prompt": (
                "A person is in a relaxed pose. As the video progresses, the "
                "character speaks naturally with subtle head movement and "
                "occasional blinks. Hand and body movements are minimal. "
                "Preserve background integrity matching the reference image."
            ),
        },
    },
    "fal-ai/sadtalker": {
        "image_arg": "source_image_url", "audio_arg": "driven_audio_url",
        "max_audio_sec": 600.0, "extras": {},
    },
    "fal-ai/dreamtalk": {
        "image_arg": "image_url", "audio_arg": "audio_url",
        "max_audio_sec": 600.0, "extras": {},
    },
}

# Cost per audio second for the cost-estimate log line.
_USD_PER_SEC: dict[str, float] = {
    "fal-ai/bytedance/omnihuman": 0.14,
    "fal-ai/bytedance/omnihuman/v1.5": 0.16,
    "fal-ai/echomimic-v3": 0.20,
    "fal-ai/sync-lipsync": 0.012,
    "fal-ai/latentsync": 0.005,
    "fal-ai/sadtalker": 0.0,
    "fal-ai/dreamtalk": 0.0,
}

# Drop avatar segments shorter than this — too short for a talking-head
# model to produce stable motion, and below the floor that fal charges.
_MIN_SEG_SEC = 0.6


@dataclass
class LipsyncSegment:
    """One contiguous avatar window in the reel timeline."""
    start_sec: float
    end_sec: float
    clip_path: Path           # absolute path to the mp4 covering this window

    def to_dict(self) -> dict:
        return {
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "clip_path": str(self.clip_path),
        }


# ─── ffmpeg helpers ──────────────────────────────────────────────────────────


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg failed: %s", " ".join(cmd))
        log.error("stderr:\n%s", result.stderr[-1500:])
        raise RuntimeError(f"ffmpeg exited {result.returncode}")


def _ensure_cache_dir() -> Path:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return _CACHE_ROOT


def _sha1_files(*paths: Path, extra: str = "") -> str:
    h = hashlib.sha1()
    for p in paths:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    if extra:
        h.update(extra.encode("utf-8"))
    return h.hexdigest()[:20]


# ─── Avatar segment computation ──────────────────────────────────────────────


def compute_avatar_segments(scenes: list[dict]) -> list[tuple[float, float, list[int]]]:
    """
    Walk scenes left-to-right, group contiguous host_avatar=True scenes
    into (start_sec, end_sec, [scene_indices]) tuples in absolute reel
    time. Drops segments shorter than _MIN_SEG_SEC.
    """
    out: list[tuple[float, float, list[int]]] = []
    t = 0.0
    seg_start: Optional[float] = None
    seg_indices: list[int] = []
    for i, s in enumerate(scenes):
        d = float(s.get("duration_sec") or 0)
        on = bool(s.get("host_avatar"))
        if on:
            if seg_start is None:
                seg_start = t
                seg_indices = []
            seg_indices.append(i)
        elif not on and seg_start is not None:
            out.append((seg_start, t, seg_indices))
            seg_start = None
            seg_indices = []
        t += d
    if seg_start is not None:
        out.append((seg_start, t, seg_indices))
    return [(a, b, idxs) for (a, b, idxs) in out if (b - a) >= _MIN_SEG_SEC]


# ─── Image / audio prep ──────────────────────────────────────────────────────


def _prepare_avatar_image(image_path: Path, dest: Path) -> Path:
    """
    Phase C Option B: pass the avatar-source.png THROUGH unchanged in
    content (no chroma plate, no cutout). We just normalise the encode
    so fal.ai gets a predictable PNG and the cache key stays stable
    across runs.
    """
    from PIL import Image  # local import; PIL is already a project dep

    src = Image.open(image_path).convert("RGB")
    src.save(dest, format="PNG", optimize=True)
    return dest


def _slice_audio(audio_path: Path, start: float, duration: float, dest: Path) -> Path:
    """Slice audio_path → mp3 starting at `start` for `duration` seconds."""
    _run_ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(audio_path),
        "-t", f"{duration:.3f}",
        "-c:a", "libmp3lame", "-q:a", "4",
        str(dest),
    ])
    return dest


# ─── fal.ai call ─────────────────────────────────────────────────────────────


def _call_talking_head_model(
    audio_chunk: Path,
    image: Path,
    model: str,
    fal_key: str,
) -> Optional[Path]:
    """
    Submit one (image, audio_chunk) pair to the fal.ai model. Returns the
    cached path of the downloaded mp4, or None on failure.

    Cache key = sha1(audio + image + model id). Identical re-runs are
    free and print "lipsync cache HIT: <key>".
    """
    cache_root = _ensure_cache_dir()
    cache_key = _sha1_files(audio_chunk, image, extra=model)
    cached = cache_root / f"{cache_key}.mp4"
    if cached.exists() and cached.stat().st_size > 1024:
        log.info("    lipsync cache HIT: %s", cache_key)
        return cached

    schema = _MODEL_SCHEMAS.get(model)
    if schema is None:
        log.error("    unknown model schema: %s", model)
        return None

    try:
        import fal_client  # type: ignore
    except Exception:
        log.error("    fal_client not installed")
        return None

    os.environ["FAL_KEY"] = fal_key

    try:
        log.info("    lipsync cache MISS: uploading inputs to fal.ai...")
        image_url = fal_client.upload_file(str(image))  # type: ignore[attr-defined]
        audio_url = fal_client.upload_file(str(audio_chunk))  # type: ignore[attr-defined]
    except Exception as exc:
        log.error("    fal.ai upload failed: %s", exc)
        return None

    args = {
        schema["image_arg"]: image_url,
        schema["audio_arg"]: audio_url,
        **schema.get("extras", {}),
    }

    try:
        log.info("    submitting %s job...", model)
        result = fal_client.subscribe(  # type: ignore[attr-defined]
            model, arguments=args, with_logs=False,
        )
    except Exception as exc:
        log.error("    fal.ai %s call failed: %s", model, exc)
        return None

    output_url = ((result or {}).get("video") or {}).get("url")
    if not output_url:
        log.error("    fal.ai returned no video; result=%s", result)
        return None

    try:
        import httpx
        log.info("    downloading talking-head clip...")
        r = httpx.get(output_url, timeout=600)
        r.raise_for_status()
        cached.write_bytes(r.content)
        log.info("    cached %s (%.1f KB)", cache_key, len(r.content) / 1024)
        return cached
    except Exception as exc:
        log.error("    download failed: %s", exc)
        return None


# ─── ffmpeg post-processing ──────────────────────────────────────────────────


def _normalize_and_concat_mp4s(parts: list[Path], dest: Path) -> Path:
    """Re-encode each chunk to canonical params then concat -c copy.

    Output is a portrait 720×1280 H.264 mp4 at _NORM_FPS, no audio. The
    re-encode is necessary even for a single chunk because fal.ai output
    dimensions vary per call.
    """
    work_dir = dest.parent / f"_norm-{dest.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)
    norm_parts: list[Path] = []
    for i, p in enumerate(parts):
        np_ = work_dir / f"norm-{i}.mp4"
        _run_ffmpeg([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(p),
            "-r", str(_NORM_FPS),
            "-vf",
            f"scale={_NORM_W}:{_NORM_H}:force_original_aspect_ratio=increase,"
            f"crop={_NORM_W}:{_NORM_H},setsar=1",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an",
            str(np_),
        ])
        norm_parts.append(np_)

    if len(norm_parts) == 1:
        # Single chunk → just rename instead of running concat.
        norm_parts[0].rename(dest)
        return dest

    list_file = dest.with_suffix(".concat.txt")
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in norm_parts) + "\n"
    )
    _run_ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(dest),
    ])
    list_file.unlink(missing_ok=True)
    return dest


# ─── Public entry point ──────────────────────────────────────────────────────


def build_lipsync_segment_clips(
    audio_path: Path,
    script: dict,
    avatar_image: Path,
    out_dir: Path,
    *,
    model: str,
    fal_key: str,
) -> list[LipsyncSegment]:
    """
    Generate one mp4 per avatar segment. Returns a list of
    `LipsyncSegment` records (start_sec, end_sec, clip_path) — one per
    contiguous run of host_avatar=true scenes. Empty list when no
    avatar segments exist.

    The mp4 is full-canvas (720×1280 portrait), no alpha. The caller
    (render.py) is responsible for staging the clip into Remotion's
    public/ folder and attaching it to the consuming scene.
    """
    if not audio_path or not audio_path.exists():
        log.warning("lipsync: audio_path missing — skipping")
        return []
    if not avatar_image or not avatar_image.exists():
        log.warning("lipsync: avatar_image missing — skipping")
        return []
    if model not in _MODEL_SCHEMAS:
        log.warning(
            "lipsync: model %s has no schema; falling back to OmniHuman base",
            model,
        )
        model = "fal-ai/bytedance/omnihuman"

    scenes = script.get("scenes", [])
    segments = compute_avatar_segments(scenes)
    total_duration = sum(float(s.get("duration_sec") or 0) for s in scenes)

    if not segments:
        log.info("lipsync: no avatar segments — skipping")
        return []

    on_seconds = sum(b - a for a, b, _ in segments)
    rate = _USD_PER_SEC.get(model)
    cost_str = f" (≈ ${on_seconds * rate:.2f} on {model})" if rate else f" ({model})"
    log.info(
        "lipsync: %d segment(s), %.1fs avatar-on / %.1fs total%s",
        len(segments), on_seconds, total_duration, cost_str,
    )

    work_dir = out_dir / "lipsync"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Phase C Option B: pass the avatar image through unchanged. Same
    # image is reused for every chunked fal.ai call so the cache stays
    # coherent across segments.
    prepared_image = work_dir / "avatar-source-prepared.png"
    _prepare_avatar_image(avatar_image, prepared_image)

    max_chunk = _MODEL_SCHEMAS[model]["max_audio_sec"]
    # Slightly under the cap so we never bump it on edge cases.
    max_chunk = max(1.0, max_chunk - 2.0)

    out_segments: list[LipsyncSegment] = []
    for seg_idx, (start, end, _scene_idxs) in enumerate(segments):
        duration = end - start
        n_chunks = max(1, int((duration + max_chunk - 0.001) // max_chunk))
        chunk_dur = duration / n_chunks
        log.info(
            "lipsync segment %d/%d: t=%.1f–%.1fs (%.1fs, %d chunk(s) × %.1fs)",
            seg_idx + 1, len(segments), start, end, duration, n_chunks, chunk_dur,
        )

        chunk_specs: list[tuple[int, Path]] = []
        for ci in range(n_chunks):
            ch_start = start + ci * chunk_dur
            ch_audio = work_dir / f"audio-seg{seg_idx}-c{ci}.mp3"
            _slice_audio(audio_path, ch_start, chunk_dur, ch_audio)
            chunk_specs.append((ci, ch_audio))

        # Submit all chunks of this segment in parallel.
        chunk_results: dict[int, Optional[Path]] = {}
        with ThreadPoolExecutor(max_workers=min(4, n_chunks)) as pool:
            futures = {
                pool.submit(
                    _call_talking_head_model,
                    audio, prepared_image, model, fal_key,
                ): idx
                for (idx, audio) in chunk_specs
            }
            for fut in futures:
                idx = futures[fut]
                try:
                    chunk_results[idx] = fut.result()
                except Exception as exc:
                    log.error("    chunk %d failed: %s", idx, exc)
                    chunk_results[idx] = None

        ordered: list[Path] = []
        any_failed = False
        for ci in range(n_chunks):
            cp = chunk_results.get(ci)
            if cp is None:
                any_failed = True
                break
            ordered.append(cp)
        if any_failed:
            log.error(
                "lipsync segment %d had failed chunk(s); skipping segment",
                seg_idx,
            )
            continue

        seg_mp4 = work_dir / f"segment-{seg_idx}.mp4"
        _normalize_and_concat_mp4s(ordered, seg_mp4)
        out_segments.append(
            LipsyncSegment(start_sec=start, end_sec=end, clip_path=seg_mp4)
        )

    log.info("lipsync: %d segment clip(s) ready", len(out_segments))
    return out_segments


# ─── Back-compat shim ────────────────────────────────────────────────────────


def build_lipsynced_avatar_track(
    audio_path: Path,
    script: dict,
    avatar_image: Path,
    out_dir: Path,
    *,
    model: str,
    fal_key: str,
) -> Optional[Path]:
    """Legacy single-track entry point.

    Phase C now emits per-segment clips via `build_lipsync_segment_clips`.
    This shim is kept so older callers don't break, but it returns the
    FIRST segment clip only (sufficient for the common 1-segment case
    in current scripts). For multi-segment reels callers should switch
    to `build_lipsync_segment_clips` directly.
    """
    segs = build_lipsync_segment_clips(
        audio_path, script, avatar_image, out_dir, model=model, fal_key=fal_key,
    )
    if not segs:
        return None
    return segs[0].clip_path
