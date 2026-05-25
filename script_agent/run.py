#!/usr/bin/env python3
# ─── run.py ───────────────────────────────────────────────────────────────────
# Script Agent — Phase 4 orchestrator.
#
# Modes:
#   python run.py --topic path/to/topic.json    → process one topic
#   python run.py --watch                        → watch sourcing_agent/outputs/
#                                                  for phase4.ready files
#
# Pipeline for each approved topic:
#   1. narrative.py  — LLM call #1 + media pipeline (images, clips, GPT art)
#   2. voiceover.py  — ElevenLabs TTS → voiceover.mp3 + word_timestamps
#   3. scene_writer.py — LLM call #2 → video_script.json (timing-corrected)
#   4. render.py     — npm run render-video → video.mp4
#
# All outputs live in:  script_agent/outputs/<YYYY-MM-DD>/<HH-MM>/<slug>/
#   ├── narrative_PROMPT.md, narrative_RESPONSE.json
#   ├── narrative.txt, voiceover.mp3, word_timestamps.json
#   ├── scene_writer_PROMPT.md, scene_writer_RESPONSE.json
#   ├── video_script.json
#   ├── video.mp4                ← final output
#   └── media/...
#
# After completion, topic.json gets `video_path` pointing to video.mp4.

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── Load .env ────────────────────────────────────────────────────────────────

_ENV_PATH = Path(__file__).parent / ".env"
# override=True so the .env file is the source of truth and stale shell
# env vars (e.g. SKIP_VOICEOVER=true left over from an earlier session)
# don't silently override the file's intent.
load_dotenv(_ENV_PATH, override=True)

CLAUDE_MODE = os.environ.get("CLAUDE_MODE", "openai").strip().lower()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "RolvCZ4e0AkAR2dzyTx0")
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")
# Default to skipping voiceover during dev iteration so we don't burn
# ElevenLabs credits on every visual tweak. Set SKIP_VOICEOVER=false in .env
# (or `SKIP_VOICEOVER=false python run.py ...` for one-off real-audio runs).
SKIP_VOICEOVER = os.environ.get("SKIP_VOICEOVER", "true").strip().lower() == "true"
SKIP_LIPSYNC = os.environ.get("SKIP_LIPSYNC", "false").strip().lower() == "true"
# Default to skipping video gen too (Veo 3.1 Fast still costs a few cents per
# clip; only fire on explicit opt-in). Set SKIP_VIDEO_GEN=false to enable.
SKIP_VIDEO_GEN = os.environ.get("SKIP_VIDEO_GEN", "true").strip().lower() == "true"
VIBE_MODEL = os.environ.get("VIBE_MODEL", os.environ.get("SCENE_WRITER_MODEL", "claude-sonnet-4-6"))
FAL_LIPSYNC_MODEL = os.environ.get("FAL_LIPSYNC_MODEL", "fal-ai/latentsync").strip()
FAL_KEY = os.environ.get("FAL_KEY", "").strip()
NARRATIVE_MODEL = os.environ.get("NARRATIVE_MODEL", "claude-opus-4-7")
SCENE_WRITER_MODEL = os.environ.get("SCENE_WRITER_MODEL", "claude-sonnet-4-6")

_SCRIPT_AGENT_ROOT = Path(__file__).parent.resolve()
SCRIPT_OUTPUTS_PATH = _SCRIPT_AGENT_ROOT / "outputs"
REMOTION_DEV_PATH = (_SCRIPT_AGENT_ROOT / os.environ.get("REMOTION_DEV_PATH", "../remotion_dev")).resolve()
SOURCING_OUTPUTS_PATH = (_SCRIPT_AGENT_ROOT / os.environ.get("SOURCING_OUTPUTS_PATH", "../sourcing_agent/outputs")).resolve()
MAX_VIDEO_DOWNLOAD_SEC = int(os.environ.get("MAX_VIDEO_DOWNLOAD_SEC", "600"))

# ─── Imports (deferred so .env is loaded first) ───────────────────────────────

from .narrative import generate_narrative
from .media.voiceover import generate_voiceover
from .scene_writer import generate_scene_script
from .render import render_video
from .vibe_planner import plan_vibe, VibeProfile


def _validate_env() -> list[str]:
    missing = []
    if CLAUDE_MODE == "api" and not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY (required when CLAUDE_MODE=api)")
    # OPENAI_API_KEY is only used for GPT-image-1 synthetic image fallback.
    # When CLAUDE_MODE=api we don't need it for LLM calls; we fall back to
    # whatever images the sourcing agent already collected.
    if CLAUDE_MODE == "openai" and not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY (required when CLAUDE_MODE=openai)")
    if not OPENAI_API_KEY:
        log.warning("⚠️  OPENAI_API_KEY not set — synthetic image generation disabled (fine if topic has enough real media)")
    if not SKIP_VOICEOVER and not ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY (or set SKIP_VOICEOVER=true to run without audio)")
    return missing


def _build_out_dir(slug: str) -> Path:
    """
    Build a fresh dated output directory for this run:
        script_agent/outputs/YYYY-MM-DD/HH-MM/<slug>/
    """
    from datetime import datetime
    now = datetime.now()
    out_dir = (
        SCRIPT_OUTPUTS_PATH
        / now.strftime("%Y-%m-%d")
        / now.strftime("%H-%M")
        / slug
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _pick_accent_color(topic: dict) -> str:
    """Heuristic: map known sources to brand colors, else default."""
    source_names = {s.get("name", "").lower() for s in topic.get("sources", [])}
    if "github" in source_names or any("github" in u.lower() for u in [topic.get("topic", "")]):
        return "#6e40c9"   # GitHub purple
    if "openai" in str(topic).lower():
        return "#10A37F"   # OpenAI green
    if "anthropic" in str(topic).lower():
        return "#D97706"   # Anthropic amber
    if "google" in str(topic).lower() or "deepmind" in str(topic).lower():
        return "#4285F4"   # Google blue
    if "meta" in str(topic).lower():
        return "#0866FF"   # Meta blue
    if "mistral" in str(topic).lower():
        return "#FF7000"   # Mistral orange
    return "#8B7FFF"        # Default lavender


# ─── Core pipeline ────────────────────────────────────────────────────────────

def process_topic(
    topic_path: Path,
    stage: str = "full",
    feedback: str = "",
) -> Path:
    """
    Run the Phase 4 pipeline for one approved topic.

    stage:
      'full'   → run all four steps (default)
      'scenes' → reuse existing narrative/voiceover, redo scene_writer + render
      'render' → reuse existing video_script.json, redo render only

    feedback:
      Free-text from the Redo dialog. Injected into the relevant prompt so
      Claude can address specific changes without starting from scratch.

    Returns the path to the rendered video.mp4.
    """
    log.info("═══════════════════════════════════════════════════")
    log.info("📽  Processing: %s", topic_path)
    log.info("═══════════════════════════════════════════════════")

    topic = json.loads(topic_path.read_text())
    slug = topic.get("slug", "unknown")
    topic_dir = topic_path.parent

    # ── Inject redo feedback into topic dict so prompts can read it ───────────
    if feedback:
        topic["_redo_feedback"] = feedback
        log.info("📝 Redo feedback (stage=%s): %s", stage, feedback[:120])

    # ── Locate previous artifacts for partial-stage runs ─────────────────────
    prev_out_dir: Optional[Path] = None
    if stage in ("scenes", "render"):
        prev_script = Path(topic.get("video_script_path", ""))
        if prev_script.exists():
            prev_out_dir = prev_script.parent
            log.info("♻️  stage=%s — reusing artifacts from %s", stage, prev_out_dir)
        else:
            log.warning(
                "stage=%s requested but no prior video_script_path found in "
                "topic.json — falling back to 'full'",
                stage,
            )
            stage = "full"

    # Independent dated output directory for this run
    out_dir = _build_out_dir(slug)
    log.info("Output dir: %s", out_dir)

    accent_color = _pick_accent_color(topic)
    log.info("Accent color: %s  |  LLM mode: %s  |  stage: %s", accent_color, CLAUDE_MODE, stage)

    # ── Step 1: Narrative + media ─────────────────────────────────────────────
    if stage == "render":
        # Load existing video_script.json — no narrative/voiceover needed
        log.info("⏭  Steps 1–3 skipped (stage=render) — loading existing script")
        prev_script_path = prev_out_dir / "video_script.json"
        script = json.loads(prev_script_path.read_text())

        # Locate existing audio file
        from .media.voiceover import VoiceoverResult, WordTimestamp
        prev_audio = prev_out_dir / "voiceover.mp3"
        prev_words = prev_out_dir / "word_timestamps.json"
        if prev_audio.exists():
            import shutil
            shutil.copy2(prev_audio, out_dir / "voiceover.mp3")
            audio_path: Optional[Path] = out_dir / "voiceover.mp3"
        else:
            audio_path = None

        if prev_words.exists():
            raw_wts = json.loads(prev_words.read_text())
            word_timestamps = [
                WordTimestamp(
                    word=w.get("word", w.get("w", "")),
                    start_sec=w.get("start_sec", w.get("start", 0.0)),
                    end_sec=w.get("end_sec", w.get("end", 0.0)),
                )
                for w in raw_wts
            ]
        else:
            word_timestamps = []

        voiceover_result = VoiceoverResult(
            audio_path=audio_path,
            word_timestamps=word_timestamps,
            total_duration_sec=sum(s.get("duration_sec", 0) for s in script.get("scenes", [])),
        )
        words_for_render = [wt.to_dict() for wt in voiceover_result.word_timestamps]

        t0 = time.time()
        video_path = render_video(
            script=script,
            audio_path=voiceover_result.audio_path,
            out_dir=out_dir,
            remotion_dev_path=REMOTION_DEV_PATH,
            voiceover_words=words_for_render,
            lipsync_segments=[],
        )
        log.info("Render done in %.1fs", time.time() - t0)

        topic["video_ready"] = True
        topic["video_path"] = str(video_path.resolve())
        topic["video_script_path"] = str((out_dir / "video_script.json").resolve())
        topic_path.write_text(json.dumps(topic, indent=2, ensure_ascii=False))
        flag = topic_dir / "phase4.ready"
        if flag.exists():
            flag.unlink()
        log.info("✅  Done (render-only): %s", video_path)
        return video_path

    # ── Steps 1+2 for 'full' and 'scenes' stages ─────────────────────────────
    t0 = time.time()
    prev_monologue: Optional[Path] = None
    if stage == "scenes" and prev_out_dir:
        # Reuse the existing narration — inject feedback into beat segmentation
        for candidate in ("narrative_monologue.txt", "narrative.txt"):
            p = prev_out_dir / candidate
            if p.exists():
                prev_monologue = p
                break

    narrative_result = generate_narrative(
        topic=topic,
        out_dir=out_dir,
        anthropic_api_key=ANTHROPIC_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        narrative_model=NARRATIVE_MODEL,
        max_video_sec=MAX_VIDEO_DOWNLOAD_SEC,
        claude_mode=CLAUDE_MODE,
        prev_monologue=prev_monologue,
    )
    log.info("Narrative done in %.1fs", time.time() - t0)

    # ── Step 1.5: Vibe planner — decide the visual aesthetic ─────────────────
    # The vibe drives color palette, motion intensity, font mood, and the
    # video-gen prompt modifiers used for the rest of the pipeline. It does
    # NOT touch the narration (that's locked).
    t0 = time.time()
    vibe = plan_vibe(
        narrative=narrative_result.narrative,
        topic=topic,
        out_dir=out_dir,
        anthropic_api_key=ANTHROPIC_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        model=VIBE_MODEL,
        claude_mode=CLAUDE_MODE,
    )
    log.info("Vibe planner done in %.1fs (%s)", time.time() - t0, vibe.vibe_name)

    # ── Step 2: Voiceover ─────────────────────────────────────────────────────
    t0 = time.time()
    if stage == "scenes" and prev_out_dir:
        # Reuse the existing voiceover audio + timestamps
        log.info("⏭  Voiceover skipped (stage=scenes) — reusing existing audio")
        from .media.voiceover import VoiceoverResult, WordTimestamp
        import shutil
        prev_audio = prev_out_dir / "voiceover.mp3"
        prev_words_file = prev_out_dir / "word_timestamps.json"
        if prev_audio.exists():
            shutil.copy2(prev_audio, out_dir / "voiceover.mp3")
            audio_path = out_dir / "voiceover.mp3"
        else:
            audio_path = None
        if prev_words_file.exists():
            raw_wts = json.loads(prev_words_file.read_text())
            wts = [
                WordTimestamp(
                    word=w.get("word", w.get("w", "")),
                    start_sec=w.get("start_sec", w.get("start", 0.0)),
                    end_sec=w.get("end_sec", w.get("end", 0.0)),
                )
                for w in raw_wts
            ]
        else:
            wts = []
        # Prefer the real audio duration from the reused word_timestamps;
        # fall back to the narrative beat estimates if none.
        if wts:
            total_duration_sec = max(w.end_sec for w in wts)
        else:
            total_duration_sec = sum(
                getattr(b, "duration_sec", 4) for b in narrative_result.beats
            )
        voiceover_result = VoiceoverResult(
            audio_path=audio_path,
            word_timestamps=wts,
            total_duration_sec=total_duration_sec,
        )
    elif SKIP_VOICEOVER:
        log.info("⏭  Voiceover skipped (SKIP_VOICEOVER=true) — rendering silent video")
        from .media.voiceover import VoiceoverResult
        word_count = len(narrative_result.narrative.split())
        estimated_sec = round(word_count / 2.5, 1)
        voiceover_result = VoiceoverResult(
            audio_path=None,
            word_timestamps=[],
            total_duration_sec=estimated_sec,
        )
    else:
        voiceover_result = generate_voiceover(
            narrative=narrative_result.narrative,
            out_dir=out_dir,
            elevenlabs_api_key=ELEVENLABS_API_KEY,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id=ELEVENLABS_MODEL_ID,
        )
        log.info("Voiceover done in %.1fs (%.1fs audio)", time.time() - t0, voiceover_result.total_duration_sec)

    # ── Step 3: Scene script ──────────────────────────────────────────────────
    t0 = time.time()
    script = generate_scene_script(
        narrative_result=narrative_result,
        voiceover_result=voiceover_result,
        topic=topic,
        out_dir=out_dir,
        anthropic_api_key=ANTHROPIC_API_KEY,
        openai_api_key=OPENAI_API_KEY,
        scene_writer_model=SCENE_WRITER_MODEL,
        accent_color=accent_color,
        claude_mode=CLAUDE_MODE,
        vibe=vibe.to_dict(),
    )
    log.info("Scene script done in %.1fs", time.time() - t0)

    # ── Step 3.5: Talking-avatar lipsync ─────────────────────────────────────
    # Skip when:
    #   • SKIP_LIPSYNC=true (visual iteration / save fal.ai credits)
    #   • SKIP_VOICEOVER=true (no audio to lipsync against)
    #   • FAL_KEY is empty
    # In those cases the renderer falls back to the still avatar with the
    # subtle Ken Burns motion the AvatarTalkingHead already provides.
    # Phase C Option B: per-segment lipsync clips. Each contiguous run of
    # host_avatar=true scenes gets a single mp4 generated from
    # avatar-source.png (full background, no chromakey). render.py
    # stages each clip into public/ and attaches it to the consuming
    # scenes via lipsync_clip_src + lipsync_clip_start_sec.
    lipsync_segments: list = []
    if SKIP_LIPSYNC:
        log.info("⏭  Lipsync skipped (SKIP_LIPSYNC=true) — using still avatar")
    elif SKIP_VOICEOVER or voiceover_result.audio_path is None:
        log.info("⏭  Lipsync skipped (no voiceover audio available)")
    elif not FAL_KEY:
        log.info("⏭  Lipsync skipped (FAL_KEY not set)")
    else:
        from .media.lipsync import build_lipsync_segment_clips
        # Phase C Option B lipsync source: the FULL avatar-source.png
        # (Spain-street background included). The model sees the same
        # frame the reel will eventually display, so the talking-head
        # output matches the still avatar pixel-for-pixel outside the
        # face region. No chromakey, no rembg cutout, no compositing.
        avatar_image = (
            REMOTION_DEV_PATH / "public" / "avatar" / "avatar-source.png"
        ).resolve()
        if not avatar_image.exists():
            log.warning(
                "Lipsync source avatar missing: %s — using still avatar",
                avatar_image,
            )
        else:
            t0 = time.time()
            try:
                lipsync_segments = build_lipsync_segment_clips(
                    audio_path=voiceover_result.audio_path,
                    script=script,
                    avatar_image=avatar_image,
                    out_dir=out_dir,
                    model=FAL_LIPSYNC_MODEL,
                    fal_key=FAL_KEY,
                )
                if lipsync_segments:
                    log.info(
                        "🗣  Lipsync done in %.1fs → %d segment clip(s)",
                        time.time() - t0, len(lipsync_segments),
                    )
            except Exception as exc:
                log.exception("Lipsync failed (will fall back to still avatar): %s", exc)
                lipsync_segments = []

    # ── Step 4: Render ────────────────────────────────────────────────────────
    # If we ran silent (SKIP_VOICEOVER), the voiceover_result has zero word
    # timestamps and the PillCaption has nothing to draw. Synthesize an
    # evenly-distributed timing track from the narrative + actual scene
    # durations so visual iteration still ships with subtitles.
    if SKIP_VOICEOVER and not voiceover_result.word_timestamps:
        from .media.voiceover import build_fake_word_timestamps
        actual_duration = sum(s.get("duration_sec", 0) for s in script.get("scenes", []))
        if actual_duration <= 0:
            actual_duration = voiceover_result.total_duration_sec
        fake_words = build_fake_word_timestamps(narrative_result.narrative, actual_duration)
        words_for_render = [wt.to_dict() for wt in fake_words]
        log.info("📝 Synthetic captions: %d words across %.1fs (silent render)",
                 len(fake_words), actual_duration)
    else:
        words_for_render = [wt.to_dict() for wt in voiceover_result.word_timestamps]

    t0 = time.time()
    video_path = render_video(
        script=script,
        audio_path=voiceover_result.audio_path,
        out_dir=out_dir,
        remotion_dev_path=REMOTION_DEV_PATH,
        voiceover_words=words_for_render,
        lipsync_segments=lipsync_segments,
    )
    log.info("Render done in %.1fs", time.time() - t0)

    # ── Mark done: update topic.json with absolute video_path ────────────────
    topic["video_ready"] = True
    topic["video_path"] = str(video_path.resolve())
    topic["video_script_path"] = str((out_dir / "video_script.json").resolve())
    topic_path.write_text(json.dumps(topic, indent=2, ensure_ascii=False))

    # Consume the phase4.ready flag
    flag = topic_dir / "phase4.ready"
    if flag.exists():
        flag.unlink()

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("✅  Done: %s", video_path)
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return video_path


# ─── Watch mode ───────────────────────────────────────────────────────────────

def watch_mode(poll_interval: int = 10) -> None:
    """
    Poll SOURCING_OUTPUTS_PATH for phase4.ready files.
    When found, run the full pipeline on the corresponding topic.json.
    """
    log.info("👁  Watch mode — polling %s every %ds", SOURCING_OUTPUTS_PATH, poll_interval)
    log.info("   Press Ctrl-C to stop.")

    processed: set[Path] = set()

    while True:
        flags = list(SOURCING_OUTPUTS_PATH.rglob("phase4.ready"))
        for flag in flags:
            if flag in processed:
                continue
            topic_path = flag.parent / "topic.json"
            if not topic_path.exists():
                log.warning("phase4.ready found but no topic.json alongside: %s", flag)
                continue

            processed.add(flag)
            try:
                process_topic(topic_path)
            except Exception as exc:
                log.exception("Pipeline failed for %s: %s", topic_path, exc)
                # Write an error marker so we don't retry in this session
                (flag.parent / "phase4.error").write_text(str(exc))

        time.sleep(poll_interval)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Script Agent — Phase 4: topic.json → video.mp4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single topic:
  python run.py --topic ../sourcing_agent/outputs/2026-05-03/15-38/some-slug/topic.json

  # Watch for approved topics automatically:
  python run.py --watch
        """,
    )
    parser.add_argument(
        "--topic",
        type=Path,
        help="Path to a specific topic.json to process",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for phase4.ready flags in sourcing_agent/outputs/",
    )
    parser.add_argument(
        "--poll",
        type=int,
        default=10,
        help="Polling interval in seconds for --watch mode (default: 10)",
    )
    parser.add_argument(
        "--stage",
        choices=["full", "scenes", "render"],
        default="full",
        help=(
            "Pipeline stage to (re)run: "
            "'full' = all steps (default), "
            "'scenes' = reuse narrative/voiceover, redo scene_writer+render, "
            "'render' = reuse video_script.json, redo render only"
        ),
    )
    parser.add_argument(
        "--feedback",
        default="",
        help="Free-text feedback to inject into the relevant prompt (used by Redo flow)",
    )
    args = parser.parse_args()

    missing = _validate_env()
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        log.error("Fill them in: %s", _ENV_PATH)
        sys.exit(1)

    if args.watch:
        watch_mode(poll_interval=args.poll)
    elif args.topic:
        topic_path = args.topic.resolve()
        if not topic_path.exists():
            log.error("topic.json not found: %s", topic_path)
            sys.exit(1)
        process_topic(topic_path, stage=args.stage, feedback=args.feedback)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
