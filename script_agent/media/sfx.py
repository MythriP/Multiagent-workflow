# ─── sfx.py ──────────────────────────────────────────────────────────────────
# Sound-effects layer for the script agent.
#
# Free SFX without an external account: every effect is synthesized on first
# call via ffmpeg filter graphs and cached under
# `script_agent/cache/sfx/<intent>.wav`. Subsequent runs reuse the cache.
#
# Public API
# ──────────
#   plan_sfx_for_scenes(scenes, *, scene_starts) -> list[SfxCue]
#       Walks the timeline and emits a list of SfxCue dataclasses. Each cue
#       has a local source path, an absolute start time, a duration, and a
#       volume in [0, 1].
#
#   build_sfx_cues_for_render(scenes, *, scene_starts, cache_dir)
#       Convenience helper that calls plan_sfx_for_scenes AND ensures the
#       referenced source files exist on disk (synthesizing any that don't).
#       Returns the same list of cues with absolute paths populated.
#
# The renderer (render.py) is responsible for staging each unique source into
# the Remotion public dir and writing the cue list onto `video_script.json`
# as `sfx_track`. DynamicReel.tsx then mounts each cue as a windowed
# <Audio> element.

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

log = logging.getLogger(__name__)

# Where synthesized SFX samples are cached on disk.
SFX_CACHE_DIRNAME = "cache/sfx"


@dataclass
class SfxCue:
    """A single SFX placement on the reel timeline."""

    intent: str                # e.g. "typing", "ui_click", "success_ding"
    src_path: Path             # absolute on-disk path to the .wav file
    start_sec: float           # offset from t=0 of the reel
    duration_sec: float        # how long the cue plays (cap on src length)
    volume: float = 0.4        # 0.0 – 1.0; defaults below 1 so SFX sit
    #                            under the voiceover instead of stepping on it

    def to_dict(self, *, src_override: Optional[str] = None) -> dict:
        return {
            "intent": self.intent,
            "src": src_override or str(self.src_path),
            "start_sec": round(self.start_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "volume": round(self.volume, 3),
        }


# ─── Synthesizers ────────────────────────────────────────────────────────────
# Each intent is a small ffmpeg filter chain producing a recognisable
# UI / mechanical sound. Tuned to sit comfortably under a voiceover:
# duration ≤ 0.5s, peak amplitude ≤ 0.5, gentle fades to avoid clicks.

# (intent, ffmpeg_input_args, ffmpeg_audio_filter, output_duration_sec)
# Inputs use `-f lavfi -i <expr>`; filters are passed via `-af`.
_SFX_RECIPES: dict[str, tuple[list[str], str, float]] = {
    "typing": (
        ["-f", "lavfi", "-i", "anoisesrc=d=0.08:c=brown:r=48000:a=0.45"],
        "highpass=f=1200,lowpass=f=4500,afade=t=in:d=0.003,afade=t=out:st=0.04:d=0.04",
        0.08,
    ),
    "tab_switch": (
        ["-f", "lavfi", "-i", "anoisesrc=d=0.32:c=pink:r=48000:a=0.55"],
        "highpass=f=400,lowpass=f=2400,"
        "afade=t=in:d=0.04,afade=t=out:st=0.16:d=0.16,"
        "volume=0.6",
        0.32,
    ),
    "ui_click": (
        ["-f", "lavfi", "-i", "anoisesrc=d=0.06:c=white:r=48000:a=0.7"],
        "bandpass=f=2500:width_type=h:w=1500,"
        "afade=t=in:d=0.003,afade=t=out:st=0.025:d=0.035,"
        "volume=0.5",
        0.06,
    ),
    "success_ding": (
        ["-f", "lavfi", "-i", "sine=frequency=1320:duration=0.45:sample_rate=48000"],
        "afade=t=in:d=0.005,afade=t=out:st=0.08:d=0.37,volume=0.32",
        0.45,
    ),
    "swoosh_in": (
        ["-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:r=48000:a=0.6"],
        "highpass=f=300,lowpass=f=1800,"
        "afade=t=in:d=0.05,afade=t=out:st=0.22:d=0.18,"
        "volume=0.5",
        0.4,
    ),
    "pop_in": (
        ["-f", "lavfi", "-i", "sine=frequency=720:duration=0.18:sample_rate=48000"],
        "afade=t=in:d=0.005,afade=t=out:st=0.05:d=0.13,volume=0.35",
        0.18,
    ),
    "whoosh_out": (
        ["-f", "lavfi", "-i", "anoisesrc=d=0.36:c=brown:r=48000:a=0.5"],
        "highpass=f=200,lowpass=f=1400,"
        "afade=t=in:d=0.02,afade=t=out:st=0.18:d=0.18,"
        "volume=0.45",
        0.36,
    ),
}


def _ensure_sfx_file(intent: str, cache_dir: Path) -> Optional[Path]:
    """
    Synthesize the named SFX into `cache_dir/<intent>.wav` if it isn't
    already cached. Returns the cached path on success, None if ffmpeg
    is missing or synthesis fails.
    """
    if intent not in _SFX_RECIPES:
        log.debug("sfx: no recipe for intent %r", intent)
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{intent}.wav"
    if out_path.exists() and out_path.stat().st_size > 1024:
        return out_path

    if shutil.which("ffmpeg") is None:
        log.warning("sfx: ffmpeg not found; cannot synthesize %r", intent)
        return None

    args, audio_filter, _dur = _SFX_RECIPES[intent]
    cmd = [
        "ffmpeg", "-y",
        *args,
        "-af", audio_filter,
        "-ar", "48000",
        "-ac", "2",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        log.warning("sfx: ffmpeg timed out synthesizing %r", intent)
        return None
    if proc.returncode != 0:
        log.warning(
            "sfx: ffmpeg failed for %r (rc=%d): %s",
            intent, proc.returncode, (proc.stderr or "")[-200:],
        )
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        return None
    log.info("sfx: synthesized %r → %s", intent, out_path.name)
    return out_path


# ─── Per-scene SFX planner ───────────────────────────────────────────────────
# Maps each scene type to a list of (intent, time_offset_within_scene,
# volume) tuples. `time_offset_within_scene` is in seconds from the
# scene's start. Special-case `chat` adds repeating typing bursts in the
# planner itself rather than a single static cue.

_SCENE_SFX_MAP: dict[str, list[tuple[str, float, float]]] = {
    "hook":               [("swoosh_in", 0.05, 0.45)],
    "split_screen":       [("tab_switch", 0.05, 0.40)],
    "floating_window":    [("ui_click", 0.10, 0.45),
                           ("pop_in", 0.18, 0.30)],
    "numbered_reveal":    [("pop_in", 0.05, 0.40)],
    "pipeline_highlight": [("ui_click", 0.05, 0.30)],
    "article_headline":   [("tab_switch", 0.05, 0.40),
                           ("ui_click", 0.30, 0.30)],
    "paper_walkthrough":  [("ui_click", 0.10, 0.25)],
    "paper_scroll":       [("whoosh_out", 0.10, 0.30)],
    "dramatic_word":      [("whoosh_out", 0.00, 0.55)],
    "headline":           [("pop_in", 0.05, 0.35)],
    "quote":              [("pop_in", 0.05, 0.30)],
    "image":              [],
    "avatar_full":        [],
    "cta":                [("success_ding", 0.10, 0.55)],
    # chat handled specially in plan_sfx_for_scenes()
    "chat":               [],
}


def plan_sfx_for_scenes(
    scenes: list[dict],
    *,
    scene_starts: Optional[list[float]] = None,
    cache_dir: Path,
    max_total_cues: int = 22,
) -> list[SfxCue]:
    """
    Walk the scene timeline and return a list of SfxCue dataclasses.

    Args:
      scenes: the script's scene list.
      scene_starts: per-scene absolute start time in seconds. If None,
        we compute starts by accumulating each scene's `duration_sec`.
      cache_dir: directory under which synthesized SFX wavs live.
      max_total_cues: hard cap on cues per reel (defensive; chat
        scenes can otherwise spam dozens of typing bursts).

    Cues whose source synthesis fails are silently dropped.
    """
    if not scenes:
        return []

    # Compute scene starts when caller didn't supply them.
    if scene_starts is None:
        scene_starts = []
        cur = 0.0
        for s in scenes:
            scene_starts.append(cur)
            cur += float(s.get("duration_sec") or 0.0)

    cues: list[SfxCue] = []

    for idx, scene in enumerate(scenes):
        if idx >= len(scene_starts):
            break
        scene_start = float(scene_starts[idx])
        scene_dur = float(scene.get("duration_sec") or 0.0)
        if scene_dur <= 0.05:
            continue
        scene_type = scene.get("type") or ""

        # Special-case: chat scenes get a sequence of typing bursts that
        # roughly mirror the user/agent turns.
        if scene_type == "chat":
            for tcue in _plan_chat_typing(scene, scene_start, scene_dur, cache_dir):
                cues.append(tcue)
            continue

        recipe = _SCENE_SFX_MAP.get(scene_type, [])
        for intent, offset, vol in recipe:
            src = _ensure_sfx_file(intent, cache_dir)
            if src is None:
                continue
            start = scene_start + max(0.0, offset)
            # Don't let an SFX cue extend past the scene; cap to whatever
            # window remains. Keep every cue ≥ 0.05s so it isn't pruned
            # to silence by the encoder.
            recipe_dur = _SFX_RECIPES[intent][2]
            dur = max(0.05, min(recipe_dur, scene_dur - max(0.0, offset)))
            cues.append(SfxCue(
                intent=intent,
                src_path=src,
                start_sec=start,
                duration_sec=dur,
                volume=vol,
            ))

    # Defensive cap.
    if len(cues) > max_total_cues:
        log.info(
            "sfx: trimming %d cues → %d (cap)", len(cues), max_total_cues,
        )
        cues = cues[:max_total_cues]

    log.info("sfx: planned %d cue(s) across %d scene(s)", len(cues), len(scenes))
    return cues


def _plan_chat_typing(
    scene: dict, scene_start: float, scene_dur: float, cache_dir: Path,
) -> list[SfxCue]:
    """
    Place one short typing burst at the start of each user turn (and a
    softer one at each agent turn). Falls back to a single cue at the
    scene start when the scene has no `turns`.
    """
    src = _ensure_sfx_file("typing", cache_dir)
    if src is None:
        return []

    turns = scene.get("turns") or []
    out: list[SfxCue] = []
    if not isinstance(turns, list) or not turns:
        out.append(SfxCue(
            intent="typing", src_path=src,
            start_sec=scene_start + 0.1,
            duration_sec=min(0.3, scene_dur),
            volume=0.45,
        ))
        return out

    # Distribute one typing burst per turn evenly across the scene.
    n = len(turns)
    if n == 0:
        return out
    step = scene_dur / n
    for i, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        offset = i * step + 0.05
        if offset >= scene_dur - 0.05:
            break
        role = (turn.get("role") or "").lower()
        vol = 0.45 if role == "user" else 0.32
        # Two quick bursts to suggest a few keypresses.
        for j in range(2):
            sub = offset + j * 0.09
            if sub >= scene_dur - 0.05:
                break
            out.append(SfxCue(
                intent="typing", src_path=src,
                start_sec=scene_start + sub,
                duration_sec=0.08,
                volume=vol,
            ))
    return out


def build_sfx_cues_for_render(
    scenes: list[dict],
    *,
    scene_starts: Optional[list[float]] = None,
    cache_dir: Path,
) -> list[SfxCue]:
    """
    Public entry point used by render.py. Same behavior as
    plan_sfx_for_scenes but with a stable name for callers.
    """
    return plan_sfx_for_scenes(
        scenes, scene_starts=scene_starts, cache_dir=cache_dir,
    )


def synthesize_all_recipes(cache_dir: Path) -> dict[str, Path]:
    """
    Eagerly synthesize every recipe and return {intent: path}. Skips
    intents whose synthesis fails. Useful for warm-up scripts and tests.
    """
    out: dict[str, Path] = {}
    for intent in _SFX_RECIPES:
        p = _ensure_sfx_file(intent, cache_dir)
        if p is not None:
            out[intent] = p
    return out


__all__ = [
    "SfxCue",
    "SFX_CACHE_DIRNAME",
    "plan_sfx_for_scenes",
    "build_sfx_cues_for_render",
    "synthesize_all_recipes",
]
