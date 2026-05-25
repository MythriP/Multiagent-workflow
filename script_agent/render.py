# ─── render.py ───────────────────────────────────────────────────────────────
# Finalises video_script.json, copies the voiceover into Remotion's public/
# directory, runs `npm run render-video`, and brings the resulting video.mp4
# back into out_dir.
#
# out_dir = script_agent/outputs/<date>/<time>/<slug>/

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _canonical_output_roots(remotion_dir: Path) -> list[Path]:
    """Folders to search for rendered video.mp4 files.

    The renderer (`test/reel-studio/scripts/render-video.ts`) writes by default
    to `<repo>/content_gen/remotion_dev/outputs/videos/...`. Older runs (and
    tests using the local reel-studio outputs folder) live under
    `remotion_dir/outputs/videos/...`. Both are checked, newest-first.
    """
    roots: list[Path] = []
    canonical = remotion_dir.parent.parent / "content_gen" / "remotion_dev" / "outputs" / "videos"
    if canonical.exists():
        roots.append(canonical)
    legacy = remotion_dir / "outputs" / "videos"
    if legacy.exists() and legacy not in roots:
        roots.append(legacy)
    return roots


def _find_rendered_video(remotion_dir: Path, slug: str) -> Path | None:
    """Locate the newest video.mp4 produced for `slug` across known output roots."""
    candidates: list[Path] = []
    for root in _canonical_output_roots(remotion_dir):
        candidates.extend(root.rglob(f"{slug}/video.mp4"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _normalise_word_timestamps(script: dict, voiceover_words: list[dict] | None) -> dict:
    """
    Reel-studio's DynamicReel expects word timestamps in the shape
    {text, start, end}. Our voiceover pipeline produces {word, start_sec, end_sec}.
    Convert the list (from voiceover_words if provided, else from script).
    """
    if voiceover_words is not None:
        words = voiceover_words
    else:
        words = script.get("word_timestamps") or []

    out: list[dict] = []
    for w in words:
        # Already in target shape?
        if "text" in w and "start" in w and "end" in w:
            out.append({"text": w["text"], "start": w["start"], "end": w["end"]})
            continue
        text = w.get("word") or w.get("text") or ""
        start = w.get("start_sec", w.get("start", 0.0))
        end = w.get("end_sec", w.get("end", start))
        if text:
            out.append({"text": text, "start": start, "end": end})

    return {**script, "word_timestamps": out}


_VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


# Anything bigger than this gets staged to public/ as a static file instead
# of embedded as a base64 data URI. Past ~3 MB, Chrome's headless renderer
# tends to OOM-crash on giant data: URLs (paper-walkthrough screenshots
# are 15-20 MB and reliably triggered "Target closed" failures).
_DATA_URI_MAX_BYTES = 3 * 1024 * 1024


def _embed_media_as_data_uris(
    script: dict, out_dir: Path, public_dir: Path, slug: str
) -> tuple[dict, list[Path]]:
    """
    Walk video_script.json and rewrite every local absolute IMAGE file path
    in one of two ways:

      • Files ≤ _DATA_URI_MAX_BYTES are embedded as base64 data URIs (fast,
        no server round-trip).
      • Files > _DATA_URI_MAX_BYTES (typically the rendered paper-walkthrough
        screenshot, which is 15-20 MB) are STAGED to public/clips/<slug>/
        and the path rewritten to `clips/<slug>/<filename>` so Remotion's
        staticFile() / <Img> can serve them. Returns the list of staged
        files so the caller can clean them up post-render.

    Video files are not handled here (stage_video_clips owns those).
    """
    media_src = out_dir / "media"
    if not media_src.exists():
        return script, []

    data_uris: dict[str, str] = {}
    staged_rewrites: dict[str, str] = {}
    staged: list[Path] = []

    clips_root = public_dir / "clips" / slug

    for f in media_src.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() in _VIDEO_EXTENSIONS:
            continue
        abs_str = str(f.resolve())
        size = f.stat().st_size
        if size > _DATA_URI_MAX_BYTES:
            clips_root.mkdir(parents=True, exist_ok=True)
            dest = clips_root / f.name
            shutil.copy2(f, dest)
            staged.append(dest)
            staged_rewrites[abs_str] = f"clips/{slug}/{f.name}"
        else:
            mime = mimetypes.guess_type(f.name)[0] or "image/png"
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            data_uris[abs_str] = f"data:{mime};base64,{b64}"

    if not data_uris and not staged_rewrites:
        return script, []

    if data_uris:
        log.info("Embedding %d image file(s) as data URIs", len(data_uris))
    if staged_rewrites:
        log.info(
            "Staged %d large image(s) → public/clips/%s/ (over %dMB threshold)",
            len(staged_rewrites), slug, _DATA_URI_MAX_BYTES // (1024 * 1024),
        )

    def _rewrite(obj):
        if isinstance(obj, dict):
            return {k: _rewrite(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_rewrite(i) for i in obj]
        if isinstance(obj, str):
            if obj in staged_rewrites:
                return staged_rewrites[obj]
            if obj in data_uris:
                return data_uris[obj]
        return obj

    return _rewrite(script), staged


def stage_video_clips(script: dict, out_dir: Path, public_dir: Path, slug: str) -> tuple[dict, list[Path]]:
    """
    Copy any .mp4/.webm/.mov files referenced in the script from out_dir/media/
    into public/clips/<slug>/<filename> so Remotion's staticFile() can resolve
    them. Rewrite each absolute path in the script to its public-relative
    equivalent (e.g. "clips/<slug>/clip-beat11.mp4"). Returns (rewritten_script,
    list_of_staged_files) so the caller can clean up after rendering.
    """
    media_src = out_dir / "media"
    if not media_src.exists():
        return script, []

    clips_root = public_dir / "clips" / slug
    rewrites: dict[str, str] = {}
    staged: list[Path] = []

    for f in media_src.iterdir():
        if not f.is_file() or f.suffix.lower() not in _VIDEO_EXTENSIONS:
            continue
        clips_root.mkdir(parents=True, exist_ok=True)
        dest = clips_root / f.name
        shutil.copy2(f, dest)
        staged.append(dest)
        rewrites[str(f.resolve())] = f"clips/{slug}/{f.name}"

    if not rewrites:
        return script, []

    log.info("Staged %d video clip(s) → public/clips/%s/", len(rewrites), slug)

    def _rewrite(obj):
        if isinstance(obj, dict):
            return {k: _rewrite(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_rewrite(i) for i in obj]
        if isinstance(obj, str) and obj in rewrites:
            return rewrites[obj]
        return obj

    return _rewrite(script), staged


def render_video(
    script: dict,
    audio_path: Path | None,
    out_dir: Path,
    remotion_dev_path: Path,
    voiceover_words: list[dict] | None = None,
    lipsync_segments: list | None = None,
) -> Path:
    """
    1. Copy voiceover → remotion_dev/public/voiceovers/<slug>.mp3  (skipped if audio_path is None)
    2. Embed media/ images as base64 data URIs inside the script dict
    3. Inject audio_file into the script (null when no audio)
    4. Write video_script.json into script_agent out_dir (pipeline artifact)
    5. Run `npm run render-video -- <abs path>`
    6. Delete staged voiceover from public/ (permanent copy stays in script_agent/outputs/)
    7. Locate video.mp4 in remotion_dev/outputs/videos/ and return that path directly —
       no copy; the video lives in remotion_dev/outputs/videos/, not in script_agent/outputs/.
    Returns the path to the rendered video inside remotion_dev/outputs/videos/.
    """
    remotion_dir = remotion_dev_path.resolve()
    public_dir = remotion_dir / "public"
    public_dir.mkdir(exist_ok=True)

    slug = script.get("slug", "video")

    # 1 — Stage voiceover in Remotion's public/voiceovers/<slug>.mp3
    #     Using a slug-specific filename prevents concurrent renders from
    #     overwriting each other. The file is cleaned up after rendering.
    staged_audio: Path | None = None
    if audio_path is not None:
        voiceovers_dir = public_dir / "voiceovers"
        voiceovers_dir.mkdir(exist_ok=True)
        staged_audio = voiceovers_dir / f"{slug}.mp3"
        shutil.copy2(audio_path, staged_audio)
        log.info("Voiceover staged: %s", staged_audio)
        audio_file_val = f"voiceovers/{slug}.mp3"
    else:
        log.info("No voiceover — rendering silent video")
        audio_file_val = None

    # 2 — Stage any video clips into public/clips/<slug>/ so OffthreadVideo
    #     can load them via staticFile() (data URIs aren't reliable for video).
    script, staged_clips = stage_video_clips(script, out_dir, public_dir, slug)

    # 2a — Embed small images as base64 data URIs; stage large ones (>3MB)
    #      into public/clips/<slug>/ so they're served as static files
    #      instead of crushing the headless Chromium with multi-MB data URLs.
    script, staged_images = _embed_media_as_data_uris(
        script, out_dir, public_dir, slug
    )
    staged_clips.extend(staged_images)

    # 2b — Normalise word_timestamps shape to {text,start,end} for DynamicReel
    script = _normalise_word_timestamps(script, voiceover_words)

    # 3 — Inject audio_file (Remotion serves /public files by base name)
    script_final = {**script, "audio_file": audio_file_val}

    # 3a — Inject avatar metadata. The Remotion AvatarOverlay only mounts
    #      when `avatar_image` is non-null, and renders a bottom-center
    #      bust during "narrator on camera" beats.
    headshot = public_dir / "avatar" / "headshot.png"
    if "avatar_image" not in script_final and headshot.exists():
        script_final["avatar_image"] = "avatar/headshot.png"

    # 3b — Phase C Option B: stage per-segment lipsync clips.
    #
    # `lipsync_segments` (when provided) is a list of LipsyncSegment
    # dataclasses, each describing one contiguous (start_sec, end_sec)
    # avatar window plus an mp4 covering it. We:
    #   1. Copy each clip into public/avatar/lipsync-<slug>-<i>.mp4.
    #   2. Walk script_final["scenes"], tagging every host_avatar=true
    #      scene that falls inside a segment with `lipsync_clip_src` +
    #      `lipsync_clip_start_sec` (offset into the segment's clip).
    # The Remotion HookCard / AvatarFullScene check for those fields
    # and play the OffthreadVideo instead of the still PNG.
    staged_lipsync: list[Path] = []
    if lipsync_segments:
        avatar_videos_dir = public_dir / "avatar"
        avatar_videos_dir.mkdir(exist_ok=True)

        # First pass: stage each clip.
        seg_records: list[tuple[float, float, str]] = []
        for i, seg in enumerate(lipsync_segments):
            src = Path(seg.clip_path) if hasattr(seg, "clip_path") else Path(seg["clip_path"])
            start = float(seg.start_sec) if hasattr(seg, "start_sec") else float(seg["start_sec"])
            end = float(seg.end_sec) if hasattr(seg, "end_sec") else float(seg["end_sec"])
            if not src.exists():
                log.warning("Lipsync clip missing on disk: %s", src)
                continue
            staged = avatar_videos_dir / f"lipsync-{slug}-{i}.mp4"
            shutil.copy2(src, staged)
            staged_lipsync.append(staged)
            seg_records.append((start, end, f"avatar/lipsync-{slug}-{i}.mp4"))
            log.info(
                "Lipsync segment %d staged: %s (%.1f KB, %.1f–%.1fs)",
                i, staged.name, staged.stat().st_size / 1024, start, end,
            )

        # Second pass: tag each consuming scene with the right clip.
        scenes_arr = script_final.get("scenes", [])
        cursor = 0.0
        for scene in scenes_arr:
            d = float(scene.get("duration_sec") or 0)
            scene_start = cursor
            scene_end = cursor + d
            cursor = scene_end
            if not bool(scene.get("host_avatar")):
                continue
            # Find the segment this scene falls inside.
            for seg_start, seg_end, src_path in seg_records:
                if scene_start >= seg_start - 1e-3 and scene_end <= seg_end + 1e-3:
                    scene["lipsync_clip_src"] = src_path
                    # Offset into the clip where THIS scene starts.
                    scene["lipsync_clip_start_sec"] = round(
                        scene_start - seg_start, 3
                    )
                    break

    # 3c — Plan + stage SFX cues.
    #
    # The SFX layer adds short UI/atmospheric cues (typing, tab-switch,
    # ui_click, success_ding, swoosh) timed to scene boundaries. Sources
    # are synthesized once and cached under script_agent/cache/sfx/. We
    # stage each unique source into public/sfx/ so DynamicReel.tsx can
    # mount it as <Audio>; the cue list itself lives on script_final
    # under "sfx_track".
    staged_sfx: list[Path] = []
    try:
        from .media.sfx import build_sfx_cues_for_render, SFX_CACHE_DIRNAME
        sfx_cache = (Path(__file__).parent / SFX_CACHE_DIRNAME).resolve()
        scenes_for_sfx = script_final.get("scenes", []) or []
        scene_starts: list[float] = []
        cur_t = 0.0
        for sc in scenes_for_sfx:
            scene_starts.append(cur_t)
            cur_t += float(sc.get("duration_sec") or 0.0)
        cues = build_sfx_cues_for_render(
            scenes_for_sfx,
            scene_starts=scene_starts,
            cache_dir=sfx_cache,
        )
        if cues:
            sfx_public_dir = public_dir / "sfx"
            sfx_public_dir.mkdir(exist_ok=True)
            unique_srcs: dict[Path, str] = {}
            sfx_track_entries: list[dict] = []
            for cue in cues:
                src = cue.src_path
                if src not in unique_srcs:
                    dest = sfx_public_dir / src.name
                    if not dest.exists():
                        shutil.copy2(src, dest)
                        staged_sfx.append(dest)
                    else:
                        # Already in public/sfx (warm cache from previous
                        # run) — still register so it gets cleaned up.
                        staged_sfx.append(dest)
                    unique_srcs[src] = f"sfx/{src.name}"
                sfx_track_entries.append(
                    cue.to_dict(src_override=unique_srcs[src])
                )
            script_final["sfx_track"] = sfx_track_entries
            log.info(
                "SFX track: %d cue(s) across %d unique source(s)",
                len(sfx_track_entries), len(unique_srcs),
            )
        else:
            script_final["sfx_track"] = []
    except Exception as exc:
        log.warning("SFX planning failed (%s); rendering without SFX", exc)
        script_final["sfx_track"] = []

    # 4 — Write video_script.json
    script_path = out_dir / "video_script.json"
    script_path.write_text(json.dumps(script_final, indent=2))
    log.info("video_script.json written: %s", script_path)

    # 5 — npm render-video
    log.info("━━ Running: npm run render-video -- %s", script_path)
    result = subprocess.run(
        ["npm", "run", "render-video", "--", str(script_path.resolve())],
        cwd=remotion_dir,
        timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Remotion render failed (exit {result.returncode})")

    # Clean up staged voiceover from public/ — the permanent copy lives in
    # script_agent/outputs/<date>/<time>/<slug>/voiceover.mp3
    if staged_audio and staged_audio.exists():
        staged_audio.unlink()
        log.info("Cleaned up staged voiceover: %s", staged_audio)

    # Clean up per-segment lipsync clips staged in public/avatar/. The
    # cached originals stay in .cache/lipsync/ and the permanent copies
    # in script_agent/outputs/<date>/<time>/<slug>/lipsync/.
    for clip in staged_lipsync:
        if clip.exists():
            clip.unlink()
    if staged_lipsync:
        log.info("Cleaned up %d staged lipsync clip(s)", len(staged_lipsync))

    # Clean up staged video clips
    for clip in staged_clips:
        if clip.exists():
            clip.unlink()
    if staged_clips:
        # Remove now-empty per-slug directory
        clips_dir = staged_clips[0].parent
        try:
            clips_dir.rmdir()
        except OSError:
            pass
        log.info("Cleaned up %d staged video clip(s)", len(staged_clips))

    # Clean up staged SFX. Cache copies stay under script_agent/cache/sfx/
    # so the next run reuses them without resynthesizing.
    for sfx_clip in staged_sfx:
        if sfx_clip.exists():
            try:
                sfx_clip.unlink()
            except OSError:
                pass
    if staged_sfx:
        try:
            (public_dir / "sfx").rmdir()
        except OSError:
            pass
        log.info("Cleaned up %d staged SFX clip(s)", len(staged_sfx))

    # 6 — Locate video.mp4 in the canonical output root and return its path.
    #     No copy — the video stays where Remotion put it.
    rendered = _find_rendered_video(remotion_dir, slug)
    if not rendered:
        # Fallback: pick newest video.mp4 across any known output root
        all_mp4s: list[Path] = []
        for root in _canonical_output_roots(remotion_dir):
            all_mp4s.extend(root.rglob("video.mp4"))
        all_mp4s.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        rendered = all_mp4s[0] if all_mp4s else None
    if not rendered:
        raise FileNotFoundError("video.mp4 not found after render — check Remotion output")

    size_mb = rendered.stat().st_size / (1024 * 1024)
    log.info("✅ video.mp4 → %s (%.1f MB)", rendered, size_mb)

    return rendered
