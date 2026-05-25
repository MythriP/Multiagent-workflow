# ─── video_gen.py ────────────────────────────────────────────────────────────
# AI video generation wrapper. Routes (prompt, optional reference image,
# duration, vibe modifiers) through fal.ai Veo 3.1 Fast and returns a local
# .mp4 path that the scene_writer can drop into the video_script.json.
#
# Why Veo 3.1 Fast: cheap and fast among production-quality models, accepts
# BOTH text-only (t2v) and image+text (i2v) prompts. Same model handles
# both modes so we don't have to swap endpoints for different scene tiers.
#
# Tiers (taxonomy used by scene_writer):
#   tier 1 — hero / named subject + reference image (i2v):
#     "the CEO walks onto a stage, gesturing"
#     -> requires reference_image_path AND a focused prompt.
#   tier 2 — specific action without reference (t2v):
#     "lab researchers comparing benchmark charts at a whiteboard"
#     -> high quality but no face anchor.
#   tier 3 — generic b-roll (t2v, ambient):
#     "abstract data visualization, low key, slow motion"
#     -> short ambient clip for backdrop use.
#
# Outputs are cached under <out_dir>/media/genvid_<hash>.mp4 so identical
# prompts on subsequent runs cost $0.

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

log = logging.getLogger(__name__)

# fal.ai model ids for Veo 3.1 Fast (verified Nov 2025).
#   text-to-video       : fal-ai/veo3.1/fast
#   image-to-video      : fal-ai/veo3.1/fast/image-to-video
# Override with VEO_MODEL_ID / VEO_I2V_MODEL_ID env vars if fal renames a route.
_DEFAULT_MODEL = os.environ.get("VEO_MODEL_ID", "fal-ai/veo3.1/fast")
_DEFAULT_I2V_MODEL = os.environ.get("VEO_I2V_MODEL_ID", "fal-ai/veo3.1/fast/image-to-video")

# Phase C Tier 2: Kling 2.5 Turbo. Cheaper, lower-quality fallback when
# Veo budget is gone or Pexels has nothing relevant. Model ids on fal.ai:
#   text-to-video  : fal-ai/kling-video/v2.5-turbo/pro/text-to-video
#   image-to-video : fal-ai/kling-video/v2.5-turbo/pro/image-to-video
_DEFAULT_KLING_MODEL = os.environ.get(
    "KLING_MODEL_ID", "fal-ai/kling-video/v2.5-turbo/pro/text-to-video"
)
_DEFAULT_KLING_I2V_MODEL = os.environ.get(
    "KLING_I2V_MODEL_ID", "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
)

# Veo accepts duration in seconds. Most reels only need short b-roll, and
# longer clips burn credits, so we hard-cap at 8s and warn if the LLM asks
# for longer.
_MAX_DURATION_SEC = 8.0
_MIN_DURATION_SEC = 4.0  # Veo's typical floor; clips shorter than this look stuttery.

# Veo 3.1 Fast (both t2v and i2v) only accepts these literal duration
# strings on fal.ai's queue. Asking for "5s" returns a 422 immediately.
_VEO_VALID_DURATIONS = ("4s", "6s", "8s")


def _snap_veo_duration(seconds: float) -> str:
    """Snap an arbitrary duration to the nearest Veo tier (4s/6s/8s)."""
    target = float(seconds)
    return min(
        _VEO_VALID_DURATIONS,
        key=lambda v: abs(int(v.rstrip("s")) - target),
    )

# Kling 2.5 Turbo is billed in fixed-duration tiers — currently 5s and 10s.
# We snap any request to the nearer tier. The "5" tier is plenty for the
# supporting-scene b-roll Tier 2 covers; the "10" tier is reserved for
# the rare longer Veo-substitute slot.
_KLING_VALID_DURATIONS = ("5", "10")

_VALID_ASPECTS = {"16:9", "9:16", "1:1"}

# Provider routing constants used by `_gen_video.provider` field.
PROVIDER_VEO = "veo"
PROVIDER_KLING = "kling"
_VALID_PROVIDERS = {PROVIDER_VEO, PROVIDER_KLING}


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class VideoGenRequest:
    """One request from scene_writer to the video generator."""

    prompt: str
    # When set, runs image-to-video (Veo 3.1 Fast supports a single ref image).
    reference_image_path: Optional[Path] = None
    duration_sec: float = 6.0
    aspect_ratio: str = "9:16"  # default vertical for reels
    # Free-form label so the cache file is human-readable. Optional.
    label: str = "generated"


@dataclass
class VideoGenResult:
    """Local path to the generated mp4 + the final composed prompt."""

    video_path: Path
    final_prompt: str
    cached: bool


# ─── Prompt composition ──────────────────────────────────────────────────────

def compose_video_prompt(
    *,
    subject_prompt: str,
    vibe_modifiers: Iterable[str] | None = None,
    extra_style: str = "",
) -> str:
    """
    Stitch a final Veo prompt out of:
      - subject_prompt:  what the camera is looking at (LLM-authored).
      - vibe_modifiers:  cinematography phrases from vibe_planner.
      - extra_style:     optional per-scene override (e.g. "no text overlays").

    The result is plain prose, ~3 short sentences. Veo handles cinematography
    cues best as a sentence about lighting + lens + motion, not a comma soup.
    """
    subject = (subject_prompt or "").strip()
    if not subject:
        raise ValueError("subject_prompt is required")

    parts: list[str] = [subject.rstrip(".") + "."]

    mods = [m.strip() for m in (vibe_modifiers or []) if m and m.strip()]
    if mods:
        # Join modifiers as one cinematography sentence.
        parts.append(", ".join(mods).rstrip(".") + ".")

    extra = (extra_style or "").strip()
    if extra:
        parts.append(extra.rstrip(".") + ".")

    # Guardrails Veo respects well as a final sentence.
    parts.append(
        "No on-screen captions. No watermarks. No logos. Photorealistic, "
        "stable framing, natural motion."
    )
    return " ".join(parts)


# ─── Cache + hashing ─────────────────────────────────────────────────────────

def _cache_key(prompt: str, ref_image: Path | None, duration_sec: float, aspect: str, model: str) -> str:
    h = hashlib.sha1()
    h.update(prompt.encode("utf-8"))
    h.update(b"|")
    if ref_image is not None and ref_image.exists():
        # Include file bytes hash so a swapped face triggers a fresh gen.
        h.update(ref_image.read_bytes()[:262144])  # first 256KB is plenty
    h.update(f"|{duration_sec:.2f}|{aspect}|{model}".encode("utf-8"))
    return h.hexdigest()[:14]


# ─── Public entry ────────────────────────────────────────────────────────────

def generate_video(
    req: VideoGenRequest,
    *,
    out_dir: Path,
    fal_key: str,
    model: str = _DEFAULT_MODEL,
) -> VideoGenResult | None:
    """
    Run Veo 3.1 Fast via fal.ai. Returns None on any error so callers can
    fall back to stock footage gracefully.

    Side effects:
      - Writes the mp4 into <out_dir>/media/genvid_<hash>.mp4.
      - Reuses an existing cache hit at the same path.
    """
    if not fal_key:
        log.info("video_gen: no FAL_KEY set — skipping generation")
        return None

    duration = max(_MIN_DURATION_SEC, min(_MAX_DURATION_SEC, float(req.duration_sec)))
    if duration != req.duration_sec:
        log.info(
            "video_gen: clamping duration %.1fs -> %.1fs (Veo bounds)",
            req.duration_sec, duration,
        )

    # Veo 3.1 Fast only accepts the literal strings 4s/6s/8s. Anything
    # else returns a 422 from the queue endpoint. Snap-and-stringify
    # before adding to the request.
    duration_label = _snap_veo_duration(duration)
    if int(duration_label.rstrip("s")) != int(round(duration)):
        log.info(
            "video_gen[veo]: snapping duration %.1fs -> %s (Veo tier)",
            duration, duration_label,
        )

    aspect = req.aspect_ratio if req.aspect_ratio in _VALID_ASPECTS else "9:16"

    final_prompt = req.prompt
    ref = req.reference_image_path
    if ref is not None and not ref.exists():
        log.warning("video_gen: reference image %s missing; falling back to t2v", ref)
        ref = None

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    key = _cache_key(final_prompt, ref, float(duration_label.rstrip("s")), aspect, model)
    dest = media_dir / f"genvid_{req.label}_{key}.mp4"
    if dest.exists() and dest.stat().st_size > 5000:
        log.info("video_gen: cache hit -> %s", dest.name)
        return VideoGenResult(video_path=dest, final_prompt=final_prompt, cached=True)

    # ── Submit to fal.ai ────────────────────────────────────────────────
    try:
        import fal_client  # type: ignore
    except ImportError:
        log.error("video_gen: fal_client not installed — `pip install fal-client`")
        return None

    os.environ.setdefault("FAL_KEY", fal_key)

    arguments: dict[str, object] = {
        "prompt": final_prompt,
        "aspect_ratio": aspect,
        # Must be the literal string "4s" / "6s" / "8s" — see
        # _snap_veo_duration above. Sending an integer or "5s" 422s.
        "duration": duration_label,
    }
    # Veo 3.1 Fast has a separate fal route for image-to-video. If a usable
    # reference image is present, swap to the i2v endpoint AND attach the
    # uploaded image URL; otherwise stay on the t2v endpoint.
    runtime_model = model
    if ref is not None:
        try:
            image_url = fal_client.upload_file(str(ref))  # type: ignore[attr-defined]
            arguments["image_url"] = image_url
            # Promote to i2v endpoint only if caller didn't pin a custom model.
            if model == _DEFAULT_MODEL:
                runtime_model = _DEFAULT_I2V_MODEL
            log.info(
                "video_gen: image-to-video (%s) ref=%s",
                runtime_model, ref.name,
            )
        except Exception as exc:
            log.warning("video_gen: ref upload failed (%s); falling back to t2v", exc)
    else:
        log.info("video_gen: text-to-video (%s) label=%s", runtime_model, req.label)

    log.info("video_gen: prompt=%s", final_prompt[:160])

    try:
        result = fal_client.subscribe(  # type: ignore[attr-defined]
            runtime_model,
            arguments=arguments,
            with_logs=False,
        )
    except Exception as exc:
        log.error("video_gen: fal.ai %s call failed: %s", runtime_model, exc)
        return None

    # Veo's response shape: {"video": {"url": "...", ...}} or {"videos": [{...}]}.
    video_url: Optional[str] = None
    if isinstance(result, dict):
        video_field = result.get("video")
        if isinstance(video_field, dict):
            video_url = video_field.get("url")
        elif isinstance(video_field, str):
            video_url = video_field
        if not video_url:
            videos = result.get("videos")
            if isinstance(videos, list) and videos:
                first = videos[0]
                if isinstance(first, dict):
                    video_url = first.get("url")
                elif isinstance(first, str):
                    video_url = first

    if not video_url:
        log.error("video_gen: fal.ai returned no video; result=%s", str(result)[:400])
        return None

    # Download the generated mp4 to the cache path.
    try:
        with httpx.stream("GET", video_url, follow_redirects=True, timeout=180) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    except Exception as exc:
        log.error("video_gen: download failed (%s): %s", video_url, exc)
        if dest.exists():
            try:
                dest.unlink()
            except Exception:
                pass
        return None

    log.info("✅ video_gen: %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    return VideoGenResult(video_path=dest, final_prompt=final_prompt, cached=False)


# ─── Kling 2.5 Turbo (Tier 2) ────────────────────────────────────────────────


def _snap_kling_duration(seconds: float) -> str:
    """Snap an arbitrary duration to the nearest Kling tier ("5" | "10")."""
    target = max(_MIN_DURATION_SEC, min(_MAX_DURATION_SEC, float(seconds)))
    return min(_KLING_VALID_DURATIONS, key=lambda v: abs(int(v) - target))


def generate_video_kling(
    req: VideoGenRequest,
    *,
    out_dir: Path,
    fal_key: str,
) -> VideoGenResult | None:
    """
    Run Kling 2.5 Turbo via fal.ai. Returns None on any error so callers
    can fall back to stock footage.

    Parallels `generate_video` (the Veo path) but speaks Kling's API
    shape: durations are bucketed to "5" or "10", aspect_ratio is the
    same set, and image-to-video uses a different endpoint.

    Cache lives in <out_dir>/media/genvid_<label>_kling_<hash>.mp4 and
    is keyed independently from Veo so swapping providers doesn't reuse
    the wrong asset.
    """
    if not fal_key:
        log.info("video_gen[kling]: no FAL_KEY set — skipping")
        return None

    duration_label = _snap_kling_duration(req.duration_sec)
    if int(duration_label) != int(req.duration_sec):
        log.info(
            "video_gen[kling]: snapping duration %.1fs -> %ss (Kling tier)",
            req.duration_sec, duration_label,
        )

    aspect = req.aspect_ratio if req.aspect_ratio in _VALID_ASPECTS else "9:16"

    final_prompt = req.prompt
    ref = req.reference_image_path
    if ref is not None and not ref.exists():
        log.warning(
            "video_gen[kling]: reference image %s missing; falling back to t2v",
            ref,
        )
        ref = None

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Use a kling-specific cache key so Veo and Kling don't collide.
    runtime_model = (
        _DEFAULT_KLING_I2V_MODEL if ref is not None else _DEFAULT_KLING_MODEL
    )
    key = _cache_key(final_prompt, ref, float(duration_label), aspect, runtime_model)
    dest = media_dir / f"genvid_{req.label}_kling_{key}.mp4"
    if dest.exists() and dest.stat().st_size > 5000:
        log.info("video_gen[kling]: cache hit -> %s", dest.name)
        return VideoGenResult(video_path=dest, final_prompt=final_prompt, cached=True)

    try:
        import fal_client  # type: ignore
    except ImportError:
        log.error("video_gen[kling]: fal_client not installed")
        return None

    os.environ.setdefault("FAL_KEY", fal_key)

    arguments: dict[str, object] = {
        "prompt": final_prompt,
        "aspect_ratio": aspect,
        "duration": duration_label,
    }
    if ref is not None:
        try:
            image_url = fal_client.upload_file(str(ref))  # type: ignore[attr-defined]
            arguments["image_url"] = image_url
            log.info(
                "video_gen[kling]: image-to-video (%s) ref=%s",
                runtime_model, ref.name,
            )
        except Exception as exc:
            log.warning(
                "video_gen[kling]: ref upload failed (%s); falling back to t2v",
                exc,
            )
            runtime_model = _DEFAULT_KLING_MODEL
    else:
        log.info(
            "video_gen[kling]: text-to-video (%s) label=%s",
            runtime_model, req.label,
        )

    log.info("video_gen[kling]: prompt=%s", final_prompt[:160])

    try:
        result = fal_client.subscribe(  # type: ignore[attr-defined]
            runtime_model,
            arguments=arguments,
            with_logs=False,
        )
    except Exception as exc:
        log.error("video_gen[kling]: fal.ai %s call failed: %s", runtime_model, exc)
        return None

    video_url: Optional[str] = None
    if isinstance(result, dict):
        video_field = result.get("video")
        if isinstance(video_field, dict):
            video_url = video_field.get("url")
        elif isinstance(video_field, str):
            video_url = video_field
        if not video_url:
            videos = result.get("videos")
            if isinstance(videos, list) and videos:
                first = videos[0]
                if isinstance(first, dict):
                    video_url = first.get("url")
                elif isinstance(first, str):
                    video_url = first

    if not video_url:
        log.error("video_gen[kling]: no video in result; %s", str(result)[:400])
        return None

    try:
        with httpx.stream("GET", video_url, follow_redirects=True, timeout=300) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    except Exception as exc:
        log.error("video_gen[kling]: download failed: %s", exc)
        if dest.exists():
            try:
                dest.unlink()
            except Exception:
                pass
        return None

    log.info("✅ video_gen[kling]: %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
    return VideoGenResult(video_path=dest, final_prompt=final_prompt, cached=False)


# ─── Convenience for scene_writer ────────────────────────────────────────────

def generate_for_beat(
    *,
    subject_prompt: str,
    out_dir: Path,
    fal_key: str,
    vibe_modifiers: Iterable[str] | None = None,
    reference_image_path: Optional[Path] = None,
    duration_sec: float = 6.0,
    aspect_ratio: str = "9:16",
    label: str = "beat",
    extra_style: str = "",
    model: str = _DEFAULT_MODEL,
    provider: str = PROVIDER_VEO,
) -> Path | None:
    """
    One-call helper for scene_writer. Composes a vibe-aware prompt and
    routes to the chosen provider. Returns the local mp4 path on
    success, None on any failure.

    `provider` selects between PROVIDER_VEO (Tier 1, hero scenes) and
    PROVIDER_KLING (Tier 2, supporting scenes). The Veo `model` arg is
    ignored when provider is Kling.
    """
    try:
        prompt = compose_video_prompt(
            subject_prompt=subject_prompt,
            vibe_modifiers=vibe_modifiers,
            extra_style=extra_style,
        )
    except ValueError as exc:
        log.warning("video_gen: %s", exc)
        return None

    req = VideoGenRequest(
        prompt=prompt,
        reference_image_path=reference_image_path,
        duration_sec=duration_sec,
        aspect_ratio=aspect_ratio,
        label=label,
    )

    if provider == PROVIDER_KLING:
        result = generate_video_kling(req, out_dir=out_dir, fal_key=fal_key)
    else:
        result = generate_video(req, out_dir=out_dir, fal_key=fal_key, model=model)
    return result.video_path if result is not None else None


# ─── Public copy-into-public helper ───────────────────────────────────────────

def _set_nested(scene: dict, dotted: str, value: str) -> None:
    """Set a nested key on a scene dict given a `pane_a.src`-style path."""
    parts = dotted.split(".")
    cur: Any = scene
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur or not isinstance(cur[p], dict):
            log.warning("video_gen: target_field %r not present on scene", dotted)
            return
        cur = cur[p]
    if isinstance(cur, dict):
        cur[parts[-1]] = value


def process_gen_video_requests(
    *,
    scenes: list[dict],
    out_dir: Path,
    slug: str,
    remotion_public_dir: Optional[Path],
    fal_key: str,
    vibe_modifiers: Iterable[str] | None = None,
    model: str = _DEFAULT_MODEL,
    max_total_clips: int = 4,
    max_veo_clips: int = 3,
) -> list[dict]:
    """
    Walk every scene; if it has a `_gen_video` block, run Veo to produce a
    clip, stage it for Remotion (if a public dir is provided), and rewrite
    the target field on the scene with the resulting path. The `_gen_video`
    block itself is removed from the final scene dict on success.

    Failure mode: the original target_field value is preserved (so always
    set a fallback path BEFORE attaching _gen_video at the writer layer).
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    veo_used = 0
    total_used = 0
    for idx, scene in enumerate(scenes):
        gen = scene.get("_gen_video")
        if not isinstance(gen, dict):
            out.append(scene)
            continue
        new_scene = {k: v for k, v in scene.items() if k != "_gen_video"}
        subject = (gen.get("subject_prompt") or "").strip()
        if not subject:
            log.warning("video_gen: scene %d _gen_video missing subject_prompt; skipping", idx)
            out.append(new_scene)
            continue
        ref_path_str = gen.get("reference_image_path")
        ref_path = Path(ref_path_str) if ref_path_str else None
        label = (gen.get("label") or f"scene{idx}").strip()
        duration = float(gen.get("duration_sec") or 6.0)
        aspect = (gen.get("aspect_ratio") or "9:16").strip()
        target_field = (gen.get("target_field") or "").strip()
        provider = (gen.get("provider") or PROVIDER_VEO).strip().lower()
        if provider not in _VALID_PROVIDERS:
            log.warning(
                "video_gen: scene %d unknown provider %r; defaulting to %s",
                idx, provider, PROVIDER_VEO,
            )
            provider = PROVIDER_VEO
        if not target_field:
            log.warning("video_gen: scene %d _gen_video missing target_field; skipping", idx)
            out.append(new_scene)
            continue

        # Phase C budget enforcement: cap total generated clips per reel
        # and the share that comes from Tier 1 (Veo). When over budget,
        # demote Veo→Kling; when over the total cap, drop the request
        # entirely (the scene keeps its fallback Pexels / image src).
        if total_used >= max_total_clips:
            log.warning(
                "video_gen: scene %d skipped — total clip cap (%d) reached",
                idx, max_total_clips,
            )
            out.append(new_scene)
            continue
        if provider == PROVIDER_VEO and veo_used >= max_veo_clips:
            log.info(
                "video_gen: scene %d demoted Veo→Kling (Veo cap %d reached)",
                idx, max_veo_clips,
            )
            provider = PROVIDER_KLING

        video_path = generate_for_beat(
            subject_prompt=subject,
            out_dir=out_dir,
            fal_key=fal_key,
            vibe_modifiers=vibe_modifiers,
            reference_image_path=ref_path if ref_path and ref_path.exists() else None,
            duration_sec=duration,
            aspect_ratio=aspect,
            label=label,
            model=model,
            provider=provider,
        )
        if video_path is None:
            log.warning(
                "video_gen: scene %d %s call failed; keeping fallback at %s",
                idx, provider, target_field,
            )
            out.append(new_scene)
            continue
        if remotion_public_dir is not None:
            try:
                final_path = stage_for_remotion(video_path, remotion_public_dir, slug)
            except Exception as exc:
                log.warning("video_gen: staging failed (%s); using local path", exc)
                final_path = str(video_path)
        else:
            final_path = str(video_path)

        _set_nested(new_scene, target_field, final_path)
        total_used += 1
        if provider == PROVIDER_VEO:
            veo_used += 1
        out.append(new_scene)
    log.info(
        "video_gen: produced %d clip(s) (Veo=%d, Kling=%d)",
        total_used, veo_used, total_used - veo_used,
    )
    return out


def stage_for_remotion(video_path: Path, remotion_public_dir: Path, slug: str) -> str:
    """
    Copy a generated mp4 into Remotion's public/clips/<slug>/ folder so
    staticFile() can pick it up. Returns the PUBLIC-RELATIVE path string
    (e.g. "clips/<slug>/<file>.mp4") that callers should embed in the
    video_script.json — Remotion's <OffthreadVideo> serves this through
    its dev-server static handler. (Returning an absolute path here would
    bypass that handler and 404 inside the bundled webpack environment.)

    Idempotent: if the destination already exists with the same size, no copy.
    """
    dest_dir = remotion_public_dir / "clips" / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video_path.name
    if not dest.exists() or dest.stat().st_size != video_path.stat().st_size:
        shutil.copy2(video_path, dest)
    return f"clips/{slug}/{video_path.name}"
