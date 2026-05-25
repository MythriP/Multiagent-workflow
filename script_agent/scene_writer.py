# ─── scene_writer.py ─────────────────────────────────────────────────────────
# Claude call #2: narrative + word timestamps + beat plan → video_script.json.
#
# After Claude produces the initial script, a timing corrector adjusts each
# scene's duration_sec to match the actual ElevenLabs word timestamps so the
# visuals are frame-accurately synced to the voice.

import json
import logging
import math
import os
import re
from pathlib import Path

from .narrative import Beat, NarrativeResult
from .media.voiceover import VoiceoverResult, WordTimestamp
from .llm import call_claude
from .paths import PROMPTS_DIR

log = logging.getLogger(__name__)

AUDIO_FILE_PLACEHOLDER = "__AUDIO_FILE__"


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "scene-writer.md").read_text()


def _beats_to_context(beats: list[Beat]) -> str:
    """Serialise the beat plan (with resolved local media paths) for Claude."""
    lines = ["BEAT PLAN (in order):"]
    for b in beats:
        media = str(b.media_path) if b.media_path else "none"
        lines.append(
            f"  Beat {b.id} [{b.beat_type}]: "
            f'text="{b.text[:80]}..." | media={media}'
        )
        # Pexels stock (still or video) — always surface so the writer can use
        # it as ambient back layer for text-only beats.
        if b.pexels_path:
            kind = "VIDEO" if b.pexels_is_video else "PHOTO"
            lines.append(
                f"      pexels_{kind}: {b.pexels_path}"
                f"  (query: {b.pexels_query!r})"
            )
        if b.extra_media_paths:
            extra = ", ".join(str(p) for p in b.extra_media_paths)
            lines.append(f"      extra_media (for montage): [{extra}]")
    return "\n".join(lines)


def _paper_anchors_block(narrative_result: "NarrativeResult") -> str:
    """Surface the paper outline (anchors + scroll image) to the scene_writer LLM."""
    media = narrative_result.media
    outline = media.paper_outline if media else None
    if not outline:
        return ""

    anchors = outline.get("anchors", [])
    img_path = media.paper_scroll
    img_h = outline.get("image_height", 0)
    if not anchors or not img_path:
        return ""

    lines = [
        "PAPER_ANCHORS — use these IDs in paper_walkthrough.stops[].anchor_id:",
        f"  PAPER_SCROLL_IMAGE: {img_path}",
        f"  Image dimensions: {outline.get('image_width', 1080)} × {img_h} px (tall)",
        "",
    ]
    for a in anchors:
        snippet = (a.get("text") or "").replace("\n", " ").strip()[:140]
        lines.append(
            f"  - id={a['id']:30s} kind={a['kind']:8s} y={a['y']:5d}  | {a['label']} — {snippet}"
        )
    lines.append("")
    lines.append(
        "Plan exactly ONE paper_walkthrough scene whose stops walk top-to-bottom"
        " through these anchors (typically: title → abstract → a figure → method →"
        " a results table → conclusion). Each stop's dwell_sec should reflect how"
        " much voice is spent on that point in the narrative."
    )
    return "\n".join(lines)


def _resolved_images_block(narrative_result: "NarrativeResult") -> str:
    """
    List every local image the pipeline resolved — both per-beat and from the
    flat MediaResult.image_map — so the LLM can guarantee EVERY image gets used.
    Also surface PAPER_SCROLL_IMAGE for the (single) paper_walkthrough scene.
    """
    media = narrative_result.media
    seen: set[str] = set()
    images: list[Path] = []

    # Per-beat resolved images (preferred order)
    for b in narrative_result.beats:
        if b.media_path and b.media_path.exists() and b.media_path.suffix.lower() in {
            ".png", ".jpg", ".jpeg", ".webp", ".gif"
        }:
            sp = str(b.media_path)
            if sp not in seen:
                seen.add(sp)
                images.append(b.media_path)
        for extra in b.extra_media_paths:
            sp = str(extra)
            if sp not in seen and extra.exists() and extra.suffix.lower() in {
                ".png", ".jpg", ".jpeg", ".webp", ".gif"
            }:
                seen.add(sp)
                images.append(extra)

    # Backstop: anything in image_map that wasn't already chosen by a beat
    for url, p in (media.image_map or {}).items():
        if not p:
            continue
        sp = str(p)
        if sp in seen:
            continue
        if not p.exists():
            continue
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        # Don't include the rendered paper_scroll image in the regular pool —
        # it's enormous and only meant for the paper_scroll scene.
        if media.paper_scroll and p == media.paper_scroll:
            continue
        seen.add(sp)
        images.append(p)

    lines: list[str] = []
    if images:
        lines.append("RESOLVED_IMAGES (every one of these MUST appear in the final reel):")
        for p in images:
            lines.append(f"  - {p}")
    else:
        lines.append("RESOLVED_IMAGES: (none — rely on text-only scenes)")

    if media.paper_scroll and media.paper_scroll.exists():
        lines.append("")
        lines.append(f"PAPER_SCROLL_IMAGE: {media.paper_scroll}")
        lines.append(
            "  → MUST place exactly ONE 'paper_walkthrough' scene that uses"
            " this image as `imageSrc`. The PAPER_ANCHORS block (above) lists"
            " the anchor IDs you must reference inside stops[].anchor_id."
            " Do NOT emit `paper_scroll` (deprecated) or any other paper type."
        )

    return "\n".join(lines)


def _build_user_message(
    narrative_result: NarrativeResult,
    voiceover_result: VoiceoverResult,
    topic: dict,
    accent_color: str,
    vibe: dict | None = None,
) -> str:
    parts: list[str] = []

    parts.append(f"TOTAL AUDIO DURATION: {voiceover_result.total_duration_sec:.2f} seconds")
    parts.append("")

    if vibe:
        parts.append("VIBE PROFILE (pass through verbatim as top-level `vibe` in output):")
        parts.append(json.dumps(vibe, indent=2))
        parts.append("")

    parts.append("NARRATIVE (full voiceover text):")
    parts.append(narrative_result.narrative)
    parts.append("")

    parts.append("WORD TIMESTAMPS (first 60 shown — full list in word_timestamps field):")
    for wt in voiceover_result.word_timestamps[:60]:
        parts.append(f"  {wt.start_sec:.2f}–{wt.end_sec:.2f}  \"{wt.word}\"")
    if len(voiceover_result.word_timestamps) > 60:
        parts.append(f"  ... ({len(voiceover_result.word_timestamps)} total words)")
    parts.append("")

    parts.append(_beats_to_context(narrative_result.beats))
    parts.append("")

    parts.append(_resolved_images_block(narrative_result))
    parts.append("")

    paper_block = _paper_anchors_block(narrative_result)
    if paper_block:
        parts.append(paper_block)
        parts.append("")

    parts.append(f"TOPIC SLUG: {topic.get('slug', '')}")
    parts.append(f"TOPIC NAME: {topic.get('topic', '')}")
    parts.append(f"CONTENT TYPE: {topic.get('content_type', 'unknown')}")
    parts.append(f"ACCENT COLOR: {accent_color}")
    parts.append("")

    # Include source text so the writer can transcribe dialogue into chat
    # scenes when the topic is a conversation-driven story (jailbreak,
    # prompt-injection, AI persona, etc.). Without this, chat scenes have to
    # be invented from thin air, which produces shallow / wrong dialogue.
    sources = topic.get("sources", []) or []
    if sources:
        parts.append("SOURCE TEXT (use this to transcribe chat dialogue when emitting `chat` scenes):")
        for src in sources[:2]:
            name = src.get("name") or "Source"
            text = src.get("text") or ""
            if not text:
                continue
            parts.append(f"--- {name} ---")
            parts.append(text[:2200])
        parts.append("")

    parts.append(
        "Produce the video_script.json. "
        "Set audio_file to '__AUDIO_FILE__' (Python will fill in the real path). "
        "Return only valid JSON."
    )

    return "\n".join(parts)


def _clean_word(s: str) -> str:
    """Strip punctuation/case for word matching."""
    return re.sub(r"[^\w]", "", s.lower())


def _find_word_subsequence(
    word_timestamps: list[WordTimestamp],
    target_words: list[str],
    start_idx: int,
) -> tuple[int, int] | None:
    """
    Find the contiguous index range in word_timestamps that matches target_words
    as a subsequence (skipping over [pause] tokens like '...'). Returns (first, last)
    or None.
    """
    if not target_words:
        return None

    cleaned_targets = [_clean_word(w) for w in target_words if _clean_word(w)]
    if not cleaned_targets:
        return None

    n = len(word_timestamps)
    # Try each potential anchor for the first target word
    for anchor in range(start_idx, n):
        if _clean_word(word_timestamps[anchor].word) != cleaned_targets[0]:
            continue
        # Walk forward, skipping pause tokens, matching subsequent target words
        ti = 1
        wi = anchor + 1
        last_match = anchor
        while ti < len(cleaned_targets) and wi < n:
            wt_clean = _clean_word(word_timestamps[wi].word)
            if not wt_clean:  # pause / ellipsis
                wi += 1
                continue
            if wt_clean == cleaned_targets[ti]:
                last_match = wi
                ti += 1
                wi += 1
            else:
                break
        if ti == len(cleaned_targets):
            return anchor, last_match
    return None


def _resolve_anchor_stop(
    st: dict,
    anchor_map: dict,
    pages_meta: list[dict],
    pdf_path: Path | None,
    image_h: int,
) -> dict | None:
    """
    Resolve one stop's {anchor_id, caption, highlight_phrase?} into the
    coordinate-bearing form consumed by PaperWalkthroughScene:
        {scrollY, highlight: {x,y,w,h}, caption}
    Returns None if the anchor can't be resolved.
    """
    VIEWPORT_FOCAL_OFFSET = 380

    aid = st.get("anchor_id")
    anchor = anchor_map.get(aid) if aid else None
    if not anchor:
        return None

    scroll_y = max(0, anchor["y"] - VIEWPORT_FOCAL_OFFSET)
    if image_h:
        scroll_y = min(scroll_y, max(0, image_h - 1920))

    highlight: dict | None = None
    phrase = (st.get("highlight_phrase") or "").strip()
    if phrase and pdf_path and pages_meta:
        page_idx = max(0, anchor.get("page", 1) - 1)
        from .media.core import find_phrase_bbox_in_canvas
        bbox = find_phrase_bbox_in_canvas(
            pdf_path,
            phrase,
            pages_meta,
            page_range=(max(0, page_idx - 1), page_idx + 2),
        )
        if bbox:
            highlight = {
                "x": bbox["x"], "y": bbox["y"],
                "w": bbox["w"], "h": bbox["h"],
            }
        else:
            log.debug("Phrase not found in PDF: %s — using anchor bbox", phrase[:40])
    if not highlight:
        highlight = {
            "x": max(40, anchor.get("x", 80)),
            "y": anchor["y"],
            "w": min(960, anchor.get("w", 900)),
            "h": min(220, anchor.get("h", 80)),
        }

    return {
        "scrollY": int(scroll_y),
        "highlight": highlight,
        "caption": (st.get("caption") or anchor["label"])[:80],
    }


def _coerce_paper_scroll_to_walkthrough(
    scenes: list[dict], narrative_result: "NarrativeResult"
) -> list[dict]:
    """
    Normalize legacy `paper_scroll` scenes into `paper_walkthrough` shape.

    The Remotion schema declares both types, but our new pipeline only
    supports paper_walkthrough end-to-end (anchor resolution, stop dwells,
    avatar policy). When the LLM forgets and emits a `paper_scroll`:
      • Rename `type` → `paper_walkthrough`.
      • Rename `paper_scroll_src` → `imageSrc` (fall back to media.paper_scroll
        if the LLM omitted it).
      • Preserve anchor-based stops if present so resolve_paper_walkthrough_scenes
        can do its normal anchor→scrollY job.
      • If no stops were provided, synthesize a single full-image stop so
        the schema still validates after anchor resolution.
    """
    if not scenes:
        return scenes
    media = narrative_result.media if narrative_result else None
    fallback_src = str(media.paper_scroll) if (media and media.paper_scroll) else ""
    out: list[dict] = []
    coerced = 0
    for s in scenes:
        if s.get("type") != "paper_scroll":
            out.append(s)
            continue
        new = dict(s)
        new["type"] = "paper_walkthrough"
        # Field rename.
        src = (
            new.pop("paper_scroll_src", None)
            or new.get("imageSrc")
            or fallback_src
        )
        if not src:
            log.warning(
                "_coerce_paper_scroll_to_walkthrough: no source image; dropping scene"
            )
            continue
        new["imageSrc"] = src
        # Drop fields the new schema doesn't know about so it can't trip
        # validation later. `stops` (with anchor_ids) is intentionally kept —
        # the resolver consumes that.
        new.pop("caption", None)
        # Ensure we have at least one stop so resolve_paper_walkthrough_scenes
        # doesn't bail out with "no resolvable stops".
        if not new.get("stops"):
            new["stops"] = [
                {
                    "anchor_id": None,
                    "scrollY": 0,
                    "dwell_sec": float(new.get("duration_sec") or 6.0),
                    "highlight_phrase": "",
                }
            ]
        out.append(new)
        coerced += 1
    if coerced:
        log.info(
            "_coerce_paper_scroll_to_walkthrough: rewrote %d legacy scene(s)", coerced
        )
    return out


def resolve_paper_walkthrough_scenes(
    scenes: list[dict],
    narrative_result: "NarrativeResult",
    word_timestamps: list[WordTimestamp],
) -> list[dict]:
    """
    Walk every paper_walkthrough scene and:
      1. Resolve each stop's anchor_id → scrollY + highlight bbox.
      2. Derive each stop's dwell_sec from the corresponding beat's voice span
         (via beat_ids[i] → narrative_result.beats[beat_id].text → word search).
      3. Set the scene's duration_sec to:
             sum(dwell_sec) + (len(stops)-1) * transition_sec
         so the walkthrough exactly fills the voice it absorbs.

    If anchor resolution fails for a stop, the stop is dropped. If all stops
    drop, the scene is replaced with a 'headline' fallback.
    """
    media = narrative_result.media
    outline = media.paper_outline if media else None
    if not outline:
        return scenes

    anchor_map = {a["id"]: a for a in outline.get("anchors", [])}
    pages_meta = outline.get("pages", [])
    image_h = outline.get("image_height", 0)
    pdf_path = media.paper_pdf_path
    beats = narrative_result.beats

    out_scenes: list[dict] = []
    for scene in scenes:
        if scene.get("type") != "paper_walkthrough":
            out_scenes.append(scene)
            continue

        raw_stops = scene.get("stops", []) or []
        beat_ids = scene.get("beat_ids") or []
        if len(beat_ids) != len(raw_stops):
            log.warning(
                "paper_walkthrough: beat_ids (%d) != stops (%d) — rebalancing",
                len(beat_ids), len(raw_stops),
            )
            if len(beat_ids) > len(raw_stops) and raw_stops:
                # More beats than stops: distribute trailing beats onto the
                # last stop (so its dwell absorbs them and we don't lose voice).
                # Conceptually, the last stop becomes a multi-beat dwell anchor.
                # We pad raw_stops by duplicating the final stop so each beat
                # has a corresponding stop entry; downstream dwell rescaling
                # then sums them — net effect = the real (final) anchor's
                # dwell holds for all trailing beats.
                last = raw_stops[-1]
                while len(raw_stops) < len(beat_ids):
                    raw_stops.append(dict(last))
            elif len(raw_stops) > len(beat_ids):
                # More stops than beats: drop trailing stops without beats
                raw_stops = raw_stops[: len(beat_ids)]

        transition_sec = float(scene.get("transition_sec", 0.8))

        resolved_stops: list[dict] = []
        for st, b_id in zip(raw_stops, beat_ids):
            base = _resolve_anchor_stop(st, anchor_map, pages_meta, pdf_path, image_h)
            if base is None:
                log.warning(
                    "paper_walkthrough: unresolved anchor_id=%s for beat_id=%s — dropping stop",
                    st.get("anchor_id"), b_id,
                )
                continue
            # Compute dwell from the matched beat's voice span
            dwell = 3.0
            if 0 <= b_id < len(beats):
                beat = beats[b_id]
                match = _find_word_subsequence(word_timestamps, beat.text.split(), 0)
                if match:
                    first_idx, last_idx = match
                    dwell = max(
                        1.5,
                        word_timestamps[last_idx].end_sec
                        - word_timestamps[first_idx].start_sec,
                    )
            base["dwell_sec"] = round(dwell, 2)
            resolved_stops.append(base)

        # Deduplicate consecutive stops at the same scrollY (often happens
        # when we padded raw_stops above). Merge their dwells so the camera
        # holds longer instead of cutting to itself.
        deduped: list[dict] = []
        for s in resolved_stops:
            if deduped and deduped[-1]["scrollY"] == s["scrollY"]:
                deduped[-1]["dwell_sec"] = round(
                    deduped[-1]["dwell_sec"] + s["dwell_sec"], 2
                )
            else:
                deduped.append(s)
        resolved_stops = deduped

        if not resolved_stops:
            log.warning("paper_walkthrough: no resolvable stops — replacing with headline fallback")
            out_scenes.append({
                "type": "headline",
                "duration_sec": scene.get("duration_sec") or 6.0,
                "kicker": "PAPER",
                "headline": "Research walkthrough.",
                "subhead": None,
                "source": scene.get("source"),
                "bg_image": str(media.paper_scroll) if media and media.paper_scroll else None,
            })
            continue

        # ── Hard caps on paper_walkthrough length ────────────────────────
        # The paper is supporting evidence, not the show. If the narrative
        # only spends a few seconds on it, keep the walkthrough tight so
        # the rest of the reel can breathe.
        #   • single stop  → up to 6.0 s (just the title shot)
        #   • multi-stop   → ≤ 4.0 s per stop, ≤ 14.0 s total dwell
        MAX_DWELL_PER_STOP = 4.0
        MAX_TOTAL_DWELL = 14.0
        SINGLE_STOP_MAX = 6.0

        if len(resolved_stops) == 1:
            d = resolved_stops[0]["dwell_sec"]
            if d > SINGLE_STOP_MAX:
                log.info(
                    "paper_walkthrough: single-stop dwell %.2fs > %.1fs cap — clamping",
                    d, SINGLE_STOP_MAX,
                )
                resolved_stops[0]["dwell_sec"] = SINGLE_STOP_MAX
        else:
            # Per-stop cap first
            for s in resolved_stops:
                if s["dwell_sec"] > MAX_DWELL_PER_STOP:
                    s["dwell_sec"] = MAX_DWELL_PER_STOP
            # Then proportionally trim to fit the total budget
            cur_total = sum(s["dwell_sec"] for s in resolved_stops)
            if cur_total > MAX_TOTAL_DWELL:
                ratio = MAX_TOTAL_DWELL / cur_total
                log.info(
                    "paper_walkthrough: total dwell %.2fs > %.1fs cap — "
                    "scaling all %d stops by %.2f",
                    cur_total, MAX_TOTAL_DWELL, len(resolved_stops), ratio,
                )
                for s in resolved_stops:
                    s["dwell_sec"] = round(max(1.5, s["dwell_sec"] * ratio), 2)

        total_dwell = sum(s["dwell_sec"] for s in resolved_stops)
        scene_duration = round(total_dwell + (len(resolved_stops) - 1) * transition_sec, 2)

        new_scene = {
            "type": "paper_walkthrough",
            "duration_sec": scene_duration,
            "imageSrc": scene.get("imageSrc") or (str(media.paper_scroll) if media.paper_scroll else ""),
            "source": scene.get("source"),
            "transition_frames": int(round(transition_sec * 30)),
            "stops": resolved_stops,
            "_beat_ids": beat_ids,  # internal: tells fix_scene_timing to skip these
        }
        out_scenes.append(new_scene)

    return out_scenes


def fix_scene_timing(
    scenes: list[dict],
    beats: list[Beat],
    word_timestamps: list[WordTimestamp],
    total_audio_sec: float,
) -> list[dict]:
    """
    Set each scene's duration_sec to the exact word_timestamps span of the
    beat(s) it consumes. Most scenes consume exactly one beat (1:1 mapping).
    Multi-beat scenes (e.g. paper_walkthrough) carry an internal `_beat_ids`
    list naming every beat they absorb; their duration spans the union.

    Each scene's duration extends to the START of the next consumed-beat span
    so transitions land on real word boundaries.
    """
    if not word_timestamps:
        log.warning("Timing correction skipped: no word_timestamps")
        return scenes

    # Pass 1: locate each beat's word range
    spans: list[tuple[float, float] | None] = []
    cursor = 0
    for beat in beats:
        words = beat.text.split()
        match = _find_word_subsequence(word_timestamps, words, cursor)
        if match is None:
            spans.append(None)
            continue
        first_idx, last_idx = match
        start_sec = word_timestamps[first_idx].start_sec
        end_sec = word_timestamps[last_idx].end_sec
        spans.append((start_sec, end_sec))
        cursor = last_idx + 1

    # Pass 2: assign beats to scenes left-to-right
    consumed: set[int] = set()
    scene_beat_ids: list[list[int]] = []
    beat_cursor = 0
    n_beats = len(beats)
    for scene in scenes:
        explicit = scene.get("_beat_ids")
        if explicit:
            ids = [b for b in explicit if 0 <= b < n_beats]
            scene_beat_ids.append(ids)
            consumed.update(ids)
            beat_cursor = max(beat_cursor, max(ids) + 1 if ids else beat_cursor)
        else:
            # Advance past any beats already consumed by previous walkthrough
            while beat_cursor < n_beats and beat_cursor in consumed:
                beat_cursor += 1
            if beat_cursor < n_beats:
                scene_beat_ids.append([beat_cursor])
                consumed.add(beat_cursor)
                beat_cursor += 1
            else:
                scene_beat_ids.append([])

    # Pass 3: compute durations from beat spans. Each scene extends to the
    # START of the NEXT scene's first beat (or total_audio_sec) so the audio
    # is fully covered with no overlap.
    corrected: list[dict] = []
    for i, scene in enumerate(scenes):
        ids = scene_beat_ids[i]
        valid_spans = [spans[j] for j in ids if j < len(spans) and spans[j] is not None]
        if not valid_spans:
            corrected.append({**scene, "duration_sec": max(1.5, scene.get("duration_sec", 4))})
            continue
        scene_start = min(s[0] for s in valid_spans)
        scene_end = max(s[1] for s in valid_spans)

        # Find the next SCENE's first beat span
        next_start: float | None = None
        for k in range(i + 1, len(scenes)):
            next_ids = scene_beat_ids[k]
            next_valid = [spans[m] for m in next_ids if m < len(spans) and spans[m] is not None]
            if next_valid:
                next_start = min(s[0] for s in next_valid)
                break
        if next_start is None:
            next_start = total_audio_sec
        scene_end = max(scene_end, next_start)

        duration = max(1.5, round(scene_end - scene_start, 2))
        new_scene = {**scene, "duration_sec": duration}
        # Strip the internal helper key before it hits the JSON / Zod
        new_scene.pop("_beat_ids", None)

        # Auto-inject video_start_sec from the consumed beat's hint when the
        # scene is rendering an inline video and the LLM didn't specify one
        # explicitly. Looks across the standard video-bearing fields used by
        # the new scene types (split_screen, floating_window, numbered_reveal)
        # plus the generic legacy `imageSrc`.
        if "video_start_sec" not in new_scene:
            video_fields = (
                "imageSrc", "media_src", "window_src",
                "top_media_src", "bottom_media_src", "diagram_src",
            )
            has_video_src = any(
                isinstance(new_scene.get(f), str)
                and new_scene[f].lower().split("?")[0].endswith(
                    (".mp4", ".webm", ".mov", ".m4v")
                )
                for f in video_fields
            )
            if has_video_src:
                for bid in ids:
                    hint = getattr(beats[bid], "video_start_hint_sec", None) if bid < len(beats) else None
                    if hint is not None and hint > 0:
                        new_scene["video_start_sec"] = round(float(hint), 2)
                        log.info(
                            "Scene %d: applying beat %d video_start_hint_sec=%.2fs",
                            i, bid, hint,
                        )
                        break

        # For paper_walkthrough: the resolver has already applied a hard cap
        # (≤14s total dwell / ≤4s per stop / ≤6s for single-stop). Honor it.
        # We only SHRINK the scene's duration here, never expand it past the
        # cap — if the consumed beats span more voice than the cap allows,
        # the trailing voice plays over the FOLLOWING scene instead, which is
        # the intended behavior ("paper as supporting evidence, not the show").
        if scene.get("type") == "paper_walkthrough":
            stops = new_scene.get("stops") or []
            transition_sec = (new_scene.get("transition_frames", 24)) / 30
            n_stops = len(stops)
            if n_stops:
                resolver_total = sum(max(0.5, s.get("dwell_sec", 3.0)) for s in stops)
                resolver_duration = resolver_total + (n_stops - 1) * transition_sec
                if duration > resolver_duration:
                    log.info(
                        "paper_walkthrough: capping duration %.2fs → %.2fs "
                        "(resolver cap); trailing voice falls onto next scene",
                        duration, resolver_duration,
                    )
                    duration = round(resolver_duration, 2)
                    new_scene["duration_sec"] = duration
                # Now rescale stops to whatever the (capped) duration is.
                dwell_budget = max(1.0, duration - (n_stops - 1) * transition_sec)
                ratio = dwell_budget / max(0.01, resolver_total)
                for s in stops:
                    s["dwell_sec"] = round(max(0.8, s.get("dwell_sec", 3.0) * ratio), 2)
        corrected.append(new_scene)

    # Drop scenes that ended up with no beats (rare; happens when all beats
    # are consumed by an earlier walkthrough).
    corrected = [s for s in corrected if s.get("duration_sec", 0) >= 1.5]

    current_total = sum(s["duration_sec"] for s in corrected)
    log.info(
        "Word-anchored timing: %d scenes total %.2fs (audio=%.2fs)",
        len(corrected), current_total, total_audio_sec,
    )
    return corrected


def generate_scene_script(
    narrative_result: NarrativeResult,
    voiceover_result: VoiceoverResult,
    topic: dict,
    out_dir: Path,
    anthropic_api_key: str,
    openai_api_key: str,
    scene_writer_model: str,
    accent_color: str = "#8B7FFF",
    claude_mode: str = "openai",
    vibe: dict | None = None,
) -> dict:
    """
    Claude call #2: produce video_script.json from all gathered context.
    Returns the parsed dict (not yet written to disk — render.py does that
    after injecting the real audio_file path).
    """
    log.info("━━ Scene writer: requesting Claude completion (mode=%s)...", claude_mode)
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(
        narrative_result, voiceover_result, topic, accent_color, vibe=vibe
    )

    raw = call_claude(
        label="scene_writer",
        system=system_prompt,
        user=user_message,
        out_dir=out_dir,
        model=scene_writer_model,
        max_tokens=16000,
        mode=claude_mode,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )

    # Save raw Claude output for debugging
    (out_dir / "scene_script_raw.json").write_text(raw)

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Claude returned invalid JSON for scene script: %s", exc)
        raise

    # ── Force the vibe into the script. The LLM is asked to pass it through
    #     verbatim, but if it didn't (or mutated it), overwrite from the
    #     authoritative source we received.
    if vibe:
        script["vibe"] = vibe

    # ── Coerce any legacy `paper_scroll` emission into the canonical
    #    `paper_walkthrough` shape. The LLM occasionally still names the old
    #    type even though the prompt forbids it; normalizing here lets the
    #    rest of the pipeline (anchor resolver, schema validator) work.
    scenes = script.get("scenes", [])
    scenes = _coerce_paper_scroll_to_walkthrough(scenes, narrative_result)
    script["scenes"] = scenes

    # ── Phase B normalisations (post-LLM cleanup, pre-timing): every step
    #    here exists because the LLM keeps emitting legacy fields the prompt
    #    no longer wants. Cheap to run, idempotent, order matters.
    scenes = _strip_scene_keyword_fields(scenes)
    scenes = _force_split_screen_horizontal(scenes)
    scenes = _normalize_numbered_reveal(scenes)
    scenes = _normalize_comparison_scenes(scenes)
    scenes = _strip_pipeline_highlight_bboxes(scenes)
    scenes = _cap_dramatic_word(scenes, vibe)
    scenes = _resolve_headline_bg_conflicts(scenes)
    script["scenes"] = scenes

    # ── Resolve paper_walkthrough anchors → coordinates + initial dwells ─
    if scenes and narrative_result.media and narrative_result.media.paper_outline:
        scenes = resolve_paper_walkthrough_scenes(
            scenes,
            narrative_result,
            voiceover_result.word_timestamps,
        )
        script["scenes"] = scenes

    # ── Timing correction: voice-anchored durations (and stop-dwell rescaling
    #     for multi-beat walkthroughs).
    if scenes and narrative_result.beats:
        scenes = fix_scene_timing(
            scenes,
            narrative_result.beats,
            voiceover_result.word_timestamps,
            voiceover_result.total_duration_sec,
        )
        script["scenes"] = scenes

    # ── CTA hard-code: closing line MUST be the canonical drop line ─────────
    scenes = _force_cta_copy(scenes)
    script["scenes"] = scenes

    # ── Block logo / brand-mark images from being used as a foreground.
    #     Even with the prompt rule, the LLM sometimes still picks the
    #     Mindgard / Anthropic / OpenAI wordmark as a full-canvas visual
    #     because it reads as "topic relevant". Catch those here and swap
    #     for a Pexels b-roll using the scene's caption as a query seed.
    scenes = _block_logo_foregrounds(scenes, out_dir)
    script["scenes"] = scenes

    # ── Auto-fill bg_media_src on text-only scenes that have none. Without
    #     this, hook / headline / quote / dramatic_word / cta scenes render
    #     against plain backgrounds and the user has explicitly asked for
    #     Pexels b-roll behind every text moment when one exists.
    scenes = _autofill_text_scene_backgrounds(scenes, out_dir)
    script["scenes"] = scenes

    # ── Split any "image" scene whose source is a Pexels video AND whose
    #     duration exceeds 3.5s into multiple ≤3s sub-scenes, each pulling
    #     a different Pexels clip. Kills "Pexels plays for 3s then black
    #     for 5s" and "three identical Pexels clips with blanks between".
    scenes = _split_long_pexels_video_scenes(scenes, out_dir)
    script["scenes"] = scenes

    # ── Cap consecutive Pexels-video image scenes at 2 in a row by
    #     replacing the 3rd+ with a Pexels still photo. The user has
    #     explicitly said "not allowed to put three continuous pixels videos".
    scenes = _cap_consecutive_pexels_videos(scenes, out_dir, max_run=1)
    script["scenes"] = scenes

    # ── AI video generation (Veo 3.1 Fast) for scenes that emitted a
    #     `_gen_video` request. Honors SKIP_VIDEO_GEN env flag and the
    #     presence of a FAL_KEY. On any failure the original fallback path
    #     the writer set on `target_field` is retained.
    scenes = _process_gen_video(scenes, out_dir, topic, vibe)
    script["scenes"] = scenes

    # ── Avatar visibility timeline: strict 3-appearance rule ────────────────
    scenes = _resolve_avatar_visibility(scenes)
    script["scenes"] = scenes

    # ── Hard cap on total reel duration. Anything over 89s gets
    #     proportionally trimmed across all scenes. Run last so it sees
    #     the post-split timeline.
    scenes = _enforce_max_reel_duration(scenes, target_sec=85.0, max_sec=89.0)
    script["scenes"] = scenes

    # ── Phase C: statement-mode timeline. Walks beats tagged
    #    `statement=True`, locates each in the voiceover word timeline,
    #    and emits a StatementOverlay segment with anchor decided by the
    #    vibe + per-scene override rules.
    if narrative_result.beats and voiceover_result.word_timestamps:
        statement_segments = _build_statement_segments(
            beats=narrative_result.beats,
            scenes=scenes,
            word_timestamps=voiceover_result.word_timestamps,
            vibe=vibe,
        )
        script["statement_segments"] = statement_segments
        if statement_segments:
            log.info(
                "📣 Statement segments: %d (anchors=%s)",
                len(statement_segments),
                [s["anchor"] for s in statement_segments],
            )

    log.info(
        "✅ Scene script: %d scenes, %.1fs total",
        len(scenes),
        sum(s.get("duration_sec", 0) for s in scenes),
    )

    return script


# ─── AI video gen (Veo 3.1 Fast) — runs only when SKIP_VIDEO_GEN!=true ──────

# Hard safety cap on Veo cost. Env-var tunable; defaults are conservative.
# Each Veo 3.1 Fast clip is ~$0.05/sec at 720p, so 4 clips * 5s = $1.00 worst
# case for first-time renders. Cache hits cost zero.
MAX_GEN_VIDEO_REQUESTS = int(os.environ.get("MAX_VIDEO_GEN_REQUESTS", "4"))
# Veo 3.1 Fast accepts only "4s", "6s", "8s" — keeping the floor at 4
# avoids the "duration too short" snap path. Cap is 8 for cost control.
GEN_VIDEO_MAX_DURATION = float(os.environ.get("VIDEO_GEN_MAX_DURATION_SEC", "6.0"))
GEN_VIDEO_MIN_DURATION = float(os.environ.get("VIDEO_GEN_MIN_DURATION_SEC", "4.0"))


def _strip_gen_video_blocks(scenes: list[dict]) -> list[dict]:
    """Remove all `_gen_video` request blocks without firing Veo."""
    out: list[dict] = []
    for s in scenes:
        if "_gen_video" in s:
            new_s = {k: v for k, v in s.items() if k != "_gen_video"}
            out.append(new_s)
        else:
            out.append(s)
    return out


def _auto_inject_hero_gen_video(
    scenes: list[dict], vibe: dict | None, *, topic: dict
) -> list[dict]:
    """
    Phase C Tier-1 auto-injection.

    The LLM is unreliable about emitting `_gen_video` blocks even when
    the prompt asks for them, so we attach Veo requests programmatically
    for the three hero slots:

      • Reactive-creator hook    → bg_media_src   (full-canvas cinematic)
      • dramatic_word scene      → bg_media_src   (full-canvas cinematic)
      • pipeline_highlight       → animated_src   (i2v from diagram_src)

    Each request is i2v when an existing image lives in the natural
    "input" field for the slot; otherwise t2v. The provider is always
    PROVIDER_VEO (Tier 1) here — Tier 2 (Kling) requests are LLM-driven
    via _gen_video.provider="kling" and stay untouched.

    Idempotent: if a scene already has `_gen_video`, leave it.
    """
    if not scenes:
        return scenes

    vibe_dict = vibe if isinstance(vibe, dict) else {}
    hook_variant = (vibe_dict.get("hook_variant") or "split_50_50").strip()
    allow_dramatic = bool(vibe_dict.get("allow_dramatic_word"))
    topic_subject = (topic.get("title") or topic.get("slug") or "the topic")

    # Helper: detect whether a string is an existing usable image path.
    def _existing_image(p: object) -> Path | None:
        if not isinstance(p, str) or not p:
            return None
        if p.startswith(("http://", "https://", "data:")):
            return None
        candidate = Path(p)
        if not candidate.is_absolute():
            return None
        if not candidate.exists():
            return None
        # Filter video extensions so we don't try to use them as i2v refs.
        if candidate.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            return None
        return candidate

    new_scenes: list[dict] = []
    for s in scenes:
        if "_gen_video" in s:
            new_scenes.append(s)
            continue
        scene_type = s.get("type")
        gen_block: dict | None = None

        # 1) Reactive-creator hook ─────────────────────────────────────────
        if scene_type == "hook" and hook_variant == "reactive_creator":
            ref = _existing_image(s.get("bg_media_src"))
            duration = max(3.0, min(5.0, float(s.get("duration_sec") or 5.0)))
            gen_block = {
                "subject_prompt": (
                    f"A cinematic, attention-grabbing opening shot for a story about "
                    f"{topic_subject}. Slow camera push-in, photographic look, "
                    "no on-screen text."
                ),
                "duration_sec": duration,
                "aspect_ratio": "9:16",
                "label": "hook-bg",
                "target_field": "bg_media_src",
                "provider": "veo",
            }
            if ref is not None:
                gen_block["reference_image_path"] = str(ref)

        # 2) dramatic_word scene ───────────────────────────────────────────
        elif scene_type == "dramatic_word" and allow_dramatic:
            ref = _existing_image(s.get("bg_media_src"))
            duration = max(3.0, min(5.0, float(s.get("duration_sec") or 4.0)))
            phrase = (s.get("word") or s.get("phrase") or topic_subject).strip()
            gen_block = {
                "subject_prompt": (
                    f"A cinematic, atmospheric shot evoking the idea of \"{phrase}\". "
                    "Photographic, slow motion, shallow depth of field, no on-screen text."
                ),
                "duration_sec": duration,
                "aspect_ratio": "9:16",
                "label": "dramatic-bg",
                "target_field": "bg_media_src",
                "provider": "veo",
            }
            if ref is not None:
                gen_block["reference_image_path"] = str(ref)

        # 3) pipeline_highlight: i2v from the diagram itself ───────────────
        elif scene_type == "pipeline_highlight":
            # Skip when the scene already has an animated source (LLM or
            # earlier auto-fill set it) or when there is no diagram to
            # animate from.
            if s.get("animated_src"):
                new_scenes.append(s)
                continue
            ref = _existing_image(s.get("diagram_src"))
            if ref is not None:
                duration = max(3.0, min(5.0, float(s.get("duration_sec") or 4.0)))
                gen_block = {
                    "subject_prompt": (
                        "Subtle, cinematic camera motion across this technical "
                        "diagram. Gentle zoom and parallax, photographic look, "
                        "no extra text or watermarks added."
                    ),
                    "reference_image_path": str(ref),
                    "duration_sec": duration,
                    "aspect_ratio": "9:16",
                    "label": "pipeline-anim",
                    "target_field": "animated_src",
                    "provider": "veo",
                }

        if gen_block is not None:
            new_s = dict(s)
            new_s["_gen_video"] = gen_block
            new_scenes.append(new_s)
            log.info(
                "video_gen auto-inject: %s on %s (%s)",
                "i2v" if "reference_image_path" in gen_block else "t2v",
                scene_type,
                gen_block["target_field"],
            )
        else:
            new_scenes.append(s)
    return new_scenes


# Fields a scene can offer up as the source image for an i2v upgrade.
# Order matters: we pick the first one that resolves to a real image.
_I2V_SOURCE_FIELDS: tuple[tuple[str, str], ...] = (
    # (source_field, target_field). Most scenes animate the same field
    # they show, so source==target. For pipeline_highlight we already
    # special-case animated_src in the hero pass.
    ("imageSrc", "imageSrc"),
    ("window_src", "window_src"),
    ("article_src", "article_src"),
    ("emotional_src", "emotional_src"),
    ("media_src", "media_src"),
    ("top_media_src", "top_media_src"),
    ("bottom_media_src", "bottom_media_src"),
)

# Scene types we will NOT auto-upgrade with general i2v. Either they
# already get a hero block, the visuals are too text-heavy, or the
# source image is huge / domain-sensitive.
_I2V_TYPE_BLOCKLIST: set[str] = {
    "hook",
    "dramatic_word",
    "pipeline_highlight",
    "avatar_full",
    "cta",
    "paper_walkthrough",
    "paper_scroll",
    "chat",
}


def _general_i2v_candidate(
    scene: dict, existing_image_fn
) -> tuple[Path, str] | None:
    """
    Return (reference_image_path, target_field) if this scene is a good
    candidate for general i2v upgrade, else None.

    A scene is a candidate iff:
      - its type is not in the blocklist,
      - it doesn't already have a `_gen_video` block,
      - it has at least one of the `_I2V_SOURCE_FIELDS` pointing at a
        real, on-disk image (not a Pexels b-roll mp4, not a logo).
    """
    if scene.get("type") in _I2V_TYPE_BLOCKLIST:
        return None
    if "_gen_video" in scene:
        return None
    # Prefer Tier-A images (article screenshots, paper figures) over
    # Pexels stock photos: walk every source field twice, first only
    # accepting non-Pexels refs, then falling back to Pexels stills if
    # none of the slots were Tier-A. This way the user gets cinematic
    # motion on EVERY image we have — Tier-A wins the slot when present,
    # Pexels stills get animated rather than playing as static stock.
    pexels_fallback: tuple[Path, str] | None = None
    for src_field, tgt_field in _I2V_SOURCE_FIELDS:
        ref = existing_image_fn(scene.get(src_field))
        if ref is None:
            continue
        if _PEXELS_ANY_RE.search(ref.name):
            if pexels_fallback is None:
                pexels_fallback = (ref, tgt_field)
            continue
        return ref, tgt_field
    return pexels_fallback


def _build_general_i2v_block(
    scene: dict, ref: Path, target_field: str, topic: dict
) -> dict:
    """Build a Veo i2v `_gen_video` block for a generic content scene."""
    duration = max(GEN_VIDEO_MIN_DURATION,
                   min(GEN_VIDEO_MAX_DURATION,
                       float(scene.get("duration_sec") or 4.0)))
    topic_subject = (topic.get("title") or topic.get("slug") or "the topic")
    # Compose a tight subject prompt anchored on the scene's own copy.
    seed = (
        scene.get("caption")
        or scene.get("headline")
        or scene.get("subhead")
        or scene.get("text")
        or scene.get("number_label")
        or scene.get("title")
        or topic_subject
    )
    seed = (seed or "").strip()
    label = f"{scene.get('type', 'scene')}-i2v"
    subject_prompt = (
        f"Subtle, cinematic camera motion across this image — gentle zoom, "
        f"parallax, slow drift — supporting the idea: \"{seed}\". "
        "Photographic look, no extra text or watermarks."
    )
    return {
        "subject_prompt": subject_prompt,
        "reference_image_path": str(ref),
        "duration_sec": duration,
        "aspect_ratio": "9:16",
        "label": label,
        "target_field": target_field,
        "provider": "veo",
    }


def _auto_inject_general_i2v(
    scenes: list[dict], *, topic: dict, max_total: int
) -> list[dict]:
    """
    Phase D extension. After the hero pass attaches Veo to the hand-picked
    slots, walk every remaining scene and attach a Veo i2v block if it
    has a real image source we can animate. Honors the per-reel total cap
    (`max_total`) so we never exceed the cost budget — heroes always win.

    The cap function (`_enforce_gen_video_caps`) still runs after as a
    final safety net.
    """
    if not scenes:
        return scenes

    def _existing_image(p: object) -> Path | None:
        if not isinstance(p, str) or not p:
            return None
        if p.startswith(("http://", "https://", "data:")):
            return None
        candidate = Path(p)
        if not candidate.is_absolute():
            return None
        if not candidate.exists():
            return None
        if candidate.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            return None
        return candidate

    used = sum(1 for s in scenes if isinstance(s.get("_gen_video"), dict))
    if used >= max_total:
        log.info(
            "video_gen general i2v: %d/%d slots already used by hero scenes; skipping",
            used, max_total,
        )
        return scenes

    new_scenes: list[dict] = []
    for s in scenes:
        if used >= max_total:
            new_scenes.append(s)
            continue
        cand = _general_i2v_candidate(s, _existing_image)
        if cand is None:
            new_scenes.append(s)
            continue
        ref, target_field = cand
        ns = dict(s)
        ns["_gen_video"] = _build_general_i2v_block(s, ref, target_field, topic)
        new_scenes.append(ns)
        used += 1
        log.info(
            "video_gen auto-inject (general i2v): %s on %s ← %s",
            target_field, s.get("type"), ref.name,
        )

    return new_scenes


def _enforce_gen_video_caps(scenes: list[dict]) -> list[dict]:
    """
    Hard safety net on Veo cost. Runs BEFORE the SKIP_VIDEO_GEN gate so
    its logs surface even on dry runs.

      • At most MAX_GEN_VIDEO_REQUESTS `_gen_video` blocks survive in
        scene order. Extras are stripped (the scene falls back to whatever
        path was set on target_field BEFORE _gen_video was attached, per
        the writer's instructions).
      • Every surviving block has its duration_sec clamped to
        [GEN_VIDEO_MIN_DURATION, GEN_VIDEO_MAX_DURATION].
    """
    kept = 0
    requested = sum(1 for s in scenes if isinstance(s.get("_gen_video"), dict))
    out: list[dict] = []
    for s in scenes:
        gen = s.get("_gen_video")
        if not isinstance(gen, dict):
            out.append(s)
            continue
        if kept >= MAX_GEN_VIDEO_REQUESTS:
            log.warning(
                "video_gen cap: dropping _gen_video on scene type=%s "
                "(already at %d requests, cap=%d)",
                s.get("type"), kept, MAX_GEN_VIDEO_REQUESTS,
            )
            out.append({k: v for k, v in s.items() if k != "_gen_video"})
            continue
        new_gen = dict(gen)
        original_dur = float(new_gen.get("duration_sec") or 4.0)
        clamped_dur = max(GEN_VIDEO_MIN_DURATION,
                          min(GEN_VIDEO_MAX_DURATION, original_dur))
        if abs(clamped_dur - original_dur) > 0.05:
            log.info(
                "video_gen cap: clamped duration %.1f→%.1f on scene type=%s",
                original_dur, clamped_dur, s.get("type"),
            )
        new_gen["duration_sec"] = clamped_dur
        new_s = dict(s)
        new_s["_gen_video"] = new_gen
        out.append(new_s)
        kept += 1
    if requested > 0:
        log.info(
            "video_gen cap: %d requested → %d kept (max=%d, dur range %.1f-%.1fs)",
            requested, kept, MAX_GEN_VIDEO_REQUESTS,
            GEN_VIDEO_MIN_DURATION, GEN_VIDEO_MAX_DURATION,
        )
    return out


def _process_gen_video(
    scenes: list[dict], out_dir: Path, topic: dict, vibe: dict | None
) -> list[dict]:
    """
    Dispatcher for AI video generation. No-op (strip blocks) when:
      - SKIP_VIDEO_GEN=true (default during dev), OR
      - FAL_KEY is missing from the environment.

    The cost cap (_enforce_gen_video_caps) ALWAYS runs first, even on
    dry runs, so log output reflects what would have been generated.

    Otherwise calls into video_gen.process_gen_video_requests with the
    vibe's video_gen_modifiers, stages clips under the Remotion public dir
    when REMOTION_DEV_PATH is set, and rewrites each scene's target_field.
    """
    if not scenes:
        return scenes
    # Phase C: programmatically attach Veo (Tier 1) requests for the three
    # hero slots before the cost cap runs. The LLM may have already
    # emitted some _gen_video blocks (e.g. Tier 2 Kling for supporting
    # scenes); we leave those alone and only fill missing hero slots.
    scenes = _auto_inject_hero_gen_video(scenes, vibe, topic=topic)
    # Phase D: also upgrade any non-hero scene that has a real image
    # source (screenshot / diagram / Playwright capture) to Veo i2v —
    # the user explicitly asked us to animate the photos we already
    # have rather than fall back to text-to-video. Capped by
    # MAX_GEN_VIDEO_REQUESTS so heroes always win the budget fight.
    scenes = _auto_inject_general_i2v(
        scenes, topic=topic, max_total=MAX_GEN_VIDEO_REQUESTS,
    )
    scenes = _enforce_gen_video_caps(scenes)
    if not any("_gen_video" in s for s in scenes):
        return scenes

    skip = os.environ.get("SKIP_VIDEO_GEN", "true").strip().lower() == "true"
    fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY") or ""
    if skip or not fal_key:
        log.info(
            "video_gen: skipping (SKIP_VIDEO_GEN=%s, fal_key=%s)",
            skip, "set" if fal_key else "missing",
        )
        return _strip_gen_video_blocks(scenes)

    try:
        from .media.video_gen import process_gen_video_requests
    except Exception as exc:
        log.warning("video_gen: import failed (%s); stripping requests", exc)
        return _strip_gen_video_blocks(scenes)

    remotion_root_env = os.environ.get("REMOTION_DEV_PATH", "").strip()
    remotion_public: Path | None = None
    if remotion_root_env:
        remotion_root = Path(remotion_root_env)
        if not remotion_root.is_absolute():
            remotion_root = (Path(__file__).parent / remotion_root).resolve()
        candidate = remotion_root / "public"
        if candidate.exists():
            remotion_public = candidate

    vibe_modifiers: list[str] = []
    if isinstance(vibe, dict):
        v_mods = vibe.get("video_gen_modifiers") or []
        if isinstance(v_mods, list):
            vibe_modifiers = [str(m) for m in v_mods]

    slug = str(topic.get("slug") or "untitled")
    return process_gen_video_requests(
        scenes=scenes,
        out_dir=out_dir,
        slug=slug,
        remotion_public_dir=remotion_public,
        fal_key=fal_key,
        vibe_modifiers=vibe_modifiers,
    )


# ─── CTA copy enforcement ───────────────────────────────────────────────────

CTA_CANONICAL_TEXT = "Follow for more drops."


def _force_cta_copy(scenes: list[dict]) -> list[dict]:
    """
    Replace every CTA scene's text with the canonical "Follow for more drops."
    The narrator can wander, the CTA cannot. We also enforce the CTA scene as
    the final scene — if the LLM put it earlier, it's still rewritten in place.
    """
    if not scenes:
        return scenes
    out = list(scenes)
    for i, s in enumerate(out):
        if s.get("type") == "cta":
            new_s = dict(s)
            new_s["text"] = CTA_CANONICAL_TEXT
            out[i] = new_s
    return out


# ─── Avatar appearances — strict 3-slot rule ─────────────────────────────────
#
# The avatar appears in EXACTLY 3 places per reel:
#   1. The opening hook (scene 0). HookCard's 50/50 layout puts the avatar
#      environment photo in the bottom pane. The Python pipeline does not
#      need to inject anything for the opening — the renderer handles it as
#      part of the hook scene itself.
#   2 & 3. Two mid-reel `avatar_full` scenes (4s each) that the pipeline
#      INSERTS into the scene list. These are full-canvas environment-photo
#      shots that intentionally pause the visual narrative.
#
# The legacy AvatarOverlay system (floating-bust cutout over every "narrator
# on camera" scene) was retired on 2026-05-13. `host_avatar` is no longer
# read by the renderer; we still stamp it as a documentation hint but
# nothing depends on it.

# Scene types that hard-block the avatar even when its time-slot matches.
# These either fill the canvas vertically or carry critical content at the
# bottom of the frame (where the bust would land).
_AVATAR_HOSTILE_TYPES: set[str] = {
    "bar_chart",
    "comparison",
    "pipeline_highlight",  # the diagram fills the canvas
    "article_headline",    # article + emotional image stack fills the canvas
}

# Minimum on-screen time for an avatar appearance, in seconds.
_AVATAR_MIN_VISIBLE_SEC = 3.0
# Maximum on-screen time for an avatar appearance, in seconds.
_AVATAR_MAX_VISIBLE_SEC = 5.0
# Opening avatar duration target.
_AVATAR_OPENING_SEC = 5.0


def _image_aspect_ratio(src: str) -> float | None:
    """Return width/height for an image path, or None if not readable.

    Retained for backward-compat callers; the new avatar rule does not use it.
    """
    try:
        path = Path(src)
        if not path.is_absolute() or not path.exists():
            return None
        ext = path.suffix.lower()
        if ext in {".mp4", ".webm", ".mov", ".m4v"}:
            return None
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        if h <= 0:
            return None
        return w / h
    except Exception:
        return None


def _pick_mid_reel_avatar_slots(
    scenes: list[dict], scene_starts: list[float], total_dur: float
) -> set[int]:
    """
    Pick the two mid-reel scenes that should host the avatar.

    Strategy:
      - Compute target play-head times at ~1/3 and ~2/3 of the reel.
      - For each target, find the nearest scene whose start is within ±3s,
        whose type is NOT in _AVATAR_HOSTILE_TYPES, and whose duration is
        already in the 3-5s sweet spot (or trim-eligible).
      - Avoid picking the very first scene (opening already covers it) or
        the very last scene (cta).
      - If we can't find a clean candidate near a target, fall back to the
        closest non-hostile scene anyway — we'd rather have 3 appearances
        in slightly-off positions than fewer than 3.
    """
    n = len(scenes)
    if n < 3:
        return set()

    # Eligible indices: not first, not last, not hostile.
    eligible_pool: list[int] = []
    for i in range(1, n - 1):
        if scenes[i].get("type") in _AVATAR_HOSTILE_TYPES:
            continue
        eligible_pool.append(i)
    if len(eligible_pool) < 2:
        # Drop the hostile filter if we don't have enough candidates.
        eligible_pool = list(range(1, n - 1))
    if not eligible_pool:
        return set()

    targets = [total_dur * 0.35, total_dur * 0.70]
    picked: list[int] = []
    used: set[int] = set()
    for t in targets:
        best_idx = None
        best_dist = float("inf")
        for i in eligible_pool:
            if i in used:
                continue
            mid_t = scene_starts[i] + float(scenes[i].get("duration_sec") or 0) / 2
            d = abs(mid_t - t)
            # Penalize candidates immediately adjacent to an already-picked slot
            if picked and any(abs(i - p) < 2 for p in picked):
                d += 6.0
            if d < best_dist:
                best_dist = d
                best_idx = i
        if best_idx is not None:
            picked.append(best_idx)
            used.add(best_idx)

    return set(picked)


_AVATAR_FULL_DURATION_SEC = 4.0


def _resolve_avatar_visibility(scenes: list[dict]) -> list[dict]:
    """
    Insert two `avatar_full` scenes at the mid-reel positions.

    The opening hook scene already shows the avatar (HookCard renders the
    environment photo in its bottom pane). We add TWO additional `avatar_full`
    scenes at roughly 35% and 70% of the reel duration. Inserted between
    existing content scenes, never adjacent to the hook or the cta, never
    immediately after each other.

    Phase C: the hook is also flagged `host_avatar=True` so lipsync.py
    treats t=0 → t=hook_dur as an avatar segment. HookCard then plays
    the OmniHuman talking-head clip in its bottom pane instead of the
    still avatar-source.png. Without this flag the first 3-4 seconds
    showed a frozen photo while the voiceover narrated the hook.

    Returns a NEW list with 2 extra scenes appended in place. `host_avatar`
    is set on the hook + the two inserted scenes; lipsync.py reads it.
    """
    if not scenes or len(scenes) < 3:
        if scenes and scenes[0].get("type") == "hook":
            scenes[0] = {**scenes[0], "host_avatar": True}
        return scenes

    n = len(scenes)
    durations = [float(s.get("duration_sec") or 0) for s in scenes]
    starts: list[float] = []
    cur = 0.0
    for d in durations:
        starts.append(cur)
        cur += d
    total_dur = cur
    if total_dur <= 0:
        return scenes

    # Eligible INSERTION positions (the index AFTER which we insert).
    # Skip 0 (don't push hook to position 1), skip n-1 (don't push cta around).
    # We want to insert AFTER scene i if scene i ends near the target time.
    targets = [total_dur * 0.35, total_dur * 0.70]
    eligible_after: list[int] = list(range(1, n - 2))
    if not eligible_after:
        log.info(
            "avatar_full insert skipped: reel too short (%d scenes)", n
        )
        return scenes

    picked_after: list[int] = []
    for t in targets:
        best = None
        best_dist = float("inf")
        for i in eligible_after:
            if i in picked_after:
                continue
            # Avoid placing two avatar slots adjacent
            if picked_after and any(abs(i - p) < 2 for p in picked_after):
                continue
            end_of_i = starts[i] + durations[i]
            d = abs(end_of_i - t)
            if d < best_dist:
                best_dist = d
                best = i
        if best is not None:
            picked_after.append(best)

    if not picked_after:
        log.info("avatar_full insert skipped: no eligible positions")
        return scenes

    # Build the new scene list by walking original scenes and injecting
    # avatar_full scenes AFTER each picked index. Tag the hook with
    # host_avatar=True so lipsync.py covers t=0 with a talking clip.
    picked_after_set = set(picked_after)
    out: list[dict] = []
    for i, scene in enumerate(scenes):
        new_scene = dict(scene)
        if i == 0 and new_scene.get("type") == "hook":
            new_scene["host_avatar"] = True
        out.append(new_scene)
        if i in picked_after_set:
            out.append(
                {
                    "type": "avatar_full",
                    "duration_sec": _AVATAR_FULL_DURATION_SEC,
                    "host_avatar": True,
                }
            )

    log.info(
        "Avatar 3-slot rule: hook (scene 0) + inserted avatar_full after "
        "indices=%s → total scenes %d → %d",
        sorted(picked_after_set), n, len(out),
    )
    return out


# ─── Auto-fill bg_media_src for text-only scenes ─────────────────────────────

# Scene types that show large-typography text and benefit from an ambient
# Pexels backdrop instead of a flat color. `chat` is included because the
# new desktop-style ChatScene only occupies the top 720px; the rest of the
# canvas is backdrop space behind the avatar bust, and a blurred Pexels
# clip there reads much better than a flat radial gradient.
_TEXT_BG_TYPES: set[str] = {
    "hook",
    "dramatic_word",
    "headline",
    "quote",
    "cta",
    "chat",
}

# Variation tokens cycled across scenes so consecutive text scenes don't all
# pull the SAME Pexels clip. Each query becomes "<base> <variation>".
_BG_VARIATIONS: list[str] = [
    "abstract dark texture",
    "soft cinematic gradient",
    "out of focus city lights",
    "moody ambient atmosphere",
    "smoke flowing slow motion",
    "glitch neon backdrop",
    "ink dispersing in water",
    "subtle particles floating",
]


def _scene_query_seed(scene: dict) -> str:
    """Build a short Pexels query seed from a text-only scene."""
    candidates = []
    for key in ("text", "hook", "headline", "subhead", "subtitle", "kicker"):
        v = scene.get(key)
        if isinstance(v, str) and v.strip():
            candidates.append(v.strip())

    # Chat scenes don't have any of the keys above — derive the seed from
    # the first user turn so the backdrop relates to what's being asked.
    if not candidates and scene.get("type") == "chat":
        turns = scene.get("turns") or []
        if isinstance(turns, list):
            for t in turns:
                if isinstance(t, dict) and t.get("role") == "user":
                    txt = t.get("text") or ""
                    if txt.strip():
                        candidates.append(txt.strip())
                        break

    if not candidates:
        return ""
    seed = " ".join(candidates)
    # Strip punctuation and keep first ~5 meaningful words.
    cleaned = re.sub(r"[^\w\s-]", " ", seed)
    words = [w for w in cleaned.split() if len(w) > 2]
    return " ".join(words[:5])


# Stop-words we never let into a Pexels query (they pull bad b-roll).
_PEXELS_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "your", "their",
    "have", "has", "had", "are", "was", "were", "will", "would", "should",
    "could", "you", "they", "them", "but", "not", "what", "when", "why",
    "how", "all", "any", "some", "more", "most", "less", "than", "then",
    "also", "very", "just", "only", "even", "much", "many", "well", "get",
    "got", "make", "made", "use", "used", "uses",
}


def _scene_pexels_seed(scene: dict, *, max_words: int = 5) -> str:
    """
    Stronger, context-aware seed for any scene → Pexels lookup.

    Preference order:
      1. Direct text fields (caption, headline, text, subhead, subtitle).
      2. `subject_prompt` (gen-video subject) if present.
      3. Pane / annotation copy on composite scenes.
      4. Chat: first user turn, then first agent turn.
      5. Beat narration (`narration_text`) as last resort.

    The returned string contains 2-`max_words` content words, lowercased,
    free of punctuation and common English stop-words. We deliberately
    avoid the generic "abstract ambient" fallback here — callers can
    decide whether to fall back further.
    """
    fragments: list[str] = []

    def _push(val):
        if isinstance(val, str) and val.strip():
            fragments.append(val.strip())

    for key in ("caption", "headline", "subhead", "subtitle", "text", "hook", "kicker"):
        _push(scene.get(key))

    # subject_prompt is set on dramatic_word + by gen_video planning.
    _push(scene.get("subject_prompt"))

    # Composite-scene panes / annotations.
    for pane_key in ("top_pane", "bottom_pane", "left_pane", "right_pane"):
        pane = scene.get(pane_key)
        if isinstance(pane, dict):
            for k in ("title", "headline", "text", "caption"):
                _push(pane.get(k))
    for ann_key in ("top_annotation", "bottom_annotation"):
        ann = scene.get(ann_key)
        if isinstance(ann, dict):
            _push(ann.get("text"))
        elif isinstance(ann, str):
            _push(ann)

    # Chat scenes.
    if scene.get("type") == "chat":
        turns = scene.get("turns") or []
        if isinstance(turns, list):
            for role in ("user", "agent"):
                for t in turns:
                    if isinstance(t, dict) and t.get("role") == role:
                        _push(t.get("text"))
                        break

    # Numbered reveal lines.
    for line_key in ("number_label", "title", "subtitle", "body"):
        _push(scene.get(line_key))

    # Last resort: narration.
    _push(scene.get("narration_text"))

    if not fragments:
        return ""
    blob = " ".join(fragments).lower()
    cleaned = re.sub(r"[^\w\s-]", " ", blob)
    words = [
        w for w in cleaned.split()
        if len(w) >= 4 and w not in _PEXELS_STOPWORDS
    ]
    # Dedupe while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for w in words:
        if w in seen:
            continue
        seen.add(w)
        deduped.append(w)
        if len(deduped) >= max_words:
            break
    return " ".join(deduped)


def _autofill_text_scene_backgrounds(
    scenes: list[dict], out_dir: Path
) -> list[dict]:
    """
    Walk the scene timeline and stamp `bg_media_src` on every text-only scene
    that doesn't already have one. Pexels VIDEO is preferred (gives the
    ambient motion behind static text); falls back to a Pexels PHOTO if no
    video matches; if even that fails, leaves the scene alone (the existing
    flat-color background remains).

    Each text scene gets a DIFFERENT variation token appended to its query
    so two consecutive hooks don't both pull the same b-roll.
    """
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not pexels_key:
        return scenes
    try:
        from .media.pexels import search_video, search_photo  # type: ignore
    except Exception:
        return scenes

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    used_pexels = _collect_pexels_paths_in_use(scenes)

    out: list[dict] = []
    var_idx = 0
    for s in scenes:
        if s.get("type") not in _TEXT_BG_TYPES or s.get("bg_media_src"):
            out.append(s)
            continue

        seed = _scene_pexels_seed(s) or _scene_query_seed(s)
        variation = _BG_VARIATIONS[var_idx % len(_BG_VARIATIONS)]
        var_idx += 1
        # Strong, scene-specific query first; only fall through to the
        # generic variation if both that AND seed-only fail.
        primary_query = f"{seed} {variation}".strip() if seed else variation
        seed_only_query = seed or variation
        path = None
        last_query = primary_query
        try:
            path = search_video(
                primary_query, pexels_key, media_dir,
                exclude_paths=used_pexels,
            )
            if path is None and seed_only_query != primary_query:
                last_query = seed_only_query
                path = search_video(
                    seed_only_query, pexels_key, media_dir,
                    exclude_paths=used_pexels,
                )
            if path is None:
                last_query = variation
                path = search_video(
                    variation, pexels_key, media_dir,
                    exclude_paths=used_pexels,
                )
            if path is None:
                last_query = variation
                path = search_photo(
                    variation, pexels_key, media_dir,
                    exclude_paths=used_pexels,
                )
        except Exception as exc:
            log.debug("Auto-fill bg lookup failed for scene %s: %s", s.get("type"), exc)

        if path is not None:
            new_s = dict(s)
            new_s["bg_media_src"] = str(path)
            out.append(new_s)
            used_pexels.add(path)
            log.info(
                "Auto-fill bg_media_src on %s: %r → %s",
                s.get("type"),
                last_query,
                path.name,
            )
        else:
            out.append(s)

    return out


# ─── Split long Pexels-video scenes ──────────────────────────────────────────

_PEXELS_VIDEO_RE = re.compile(r"pexels[-_]video", re.IGNORECASE)
# Catches pexels-video-*.mp4 AND pexels-photo-*.jpg.
_PEXELS_ANY_RE = re.compile(r"pexels[-_](video|photo)", re.IGNORECASE)


def _collect_pexels_paths_in_use(scenes: list[dict]) -> set[Path]:
    """
    Walk every scene's media field and return the set of Pexels asset
    paths already referenced. Used as `exclude_paths` on subsequent
    Pexels lookups so a single reel never repeats the same clip.
    """
    used: set[Path] = set()
    keys = (
        "imageSrc", "media_src", "window_src", "diagram_src",
        "top_media_src", "bottom_media_src", "article_src", "emotional_src",
        "bg_media_src", "animated_src",
    )
    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in keys and isinstance(v, str) and v:
                    if not v.startswith(("data:", "http://", "https://")):
                        if _PEXELS_ANY_RE.search(v):
                            try:
                                p = Path(v)
                                if p.is_absolute():
                                    used.add(p)
                                else:
                                    # Strip the public/clips/<slug>/ prefix
                                    used.add(Path(p.name))
                            except Exception:
                                pass
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
    for s in scenes:
        _walk(s)
    return used
_PEXELS_VIDEO_MAX_SEC = 3.0
# Variation tokens specifically for IMAGE-scene foreground b-roll. Different
# vibe than the backdrop list above to maximise visual diversity.
_FG_VARIATIONS: list[str] = [
    "wide shot",
    "close up macro",
    "aerial drone",
    "slow motion detail",
    "abstract motion",
    "cinematic ambient",
    "time lapse subtle",
]


def _split_long_pexels_video_scenes(
    scenes: list[dict], out_dir: Path
) -> list[dict]:
    """
    For every "image" scene whose imageSrc is a Pexels video AND whose
    duration_sec is more than 3.5 seconds, split it into ⌈duration / 3⌉
    sub-scenes ≤3s each. Each sub-scene fetches a DIFFERENT Pexels clip via
    a variation token so the viewer doesn't see the same footage repeating.

    If we can't fetch enough variants (no Pexels key, network failure), we
    still split the durations but reuse the original clip — better than a
    blank screen.
    """
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    try:
        from .media.pexels import search_video  # type: ignore
    except Exception:
        search_video = None  # type: ignore

    used_pexels = _collect_pexels_paths_in_use(scenes)

    out: list[dict] = []
    for s in scenes:
        if s.get("type") != "image":
            out.append(s)
            continue
        src = s.get("imageSrc") or ""
        if not _PEXELS_VIDEO_RE.search(src):
            out.append(s)
            continue
        dur = float(s.get("duration_sec", 0))
        if dur <= _PEXELS_VIDEO_MAX_SEC + 0.5:
            out.append(s)
            continue

        n_subs = max(2, math.ceil(dur / _PEXELS_VIDEO_MAX_SEC))
        sub_dur = round(dur / n_subs, 2)

        # Build clip list — first sub uses the original clip, rest are
        # different Pexels videos. Use the same context-aware seed as the
        # auto-bg fill so we get scene-specific b-roll rather than the
        # generic "abstract ambient".
        seed = _scene_pexels_seed(s) or (s.get("caption") or "").strip() or "abstract ambient"
        clips: list[str] = [src]
        if pexels_key and search_video is not None:
            for v_idx in range(1, n_subs):
                variation = _FG_VARIATIONS[(v_idx - 1) % len(_FG_VARIATIONS)]
                q = f"{seed} {variation}".strip()
                try:
                    p = search_video(
                        q, pexels_key, media_dir,
                        exclude_paths=used_pexels,
                    )
                except Exception:
                    p = None
                if p is not None and str(p) not in clips:
                    clips.append(str(p))
                    used_pexels.add(p)
                else:
                    clips.append(src)
        else:
            clips.extend([src] * (n_subs - 1))

        log.info(
            "Splitting long Pexels-video scene (%.1fs) → %d × %.2fs sub-scenes (%d unique clips)",
            dur,
            n_subs,
            sub_dur,
            len({c for c in clips}),
        )

        for k in range(n_subs):
            new_s = dict(s)
            new_s["duration_sec"] = sub_dur
            new_s["imageSrc"] = clips[k] if k < len(clips) else src
            out.append(new_s)

    return out


# ─── Logo / brand-mark detection & replacement ───────────────────────────────


_LOGO_NAME_RE = re.compile(
    r"(logo|brand|wordmark|favicon|icon|arxiv|github|twitter|"
    r"openai|anthropic|mindgard|sonnet|claude-mark)",
    re.IGNORECASE,
)


def _looks_like_logo(path: Path) -> bool:
    """
    Heuristic: does this image look like a brand mark / logo / wordmark?

    Signals (any single signal triggers a True):
      • Filename matches a known brand token (logo, wordmark, arxiv,
        github, openai, anthropic, mindgard, …).
      • Image short side ≤ 600 px AND aspect within [0.5, 2.0] (square-ish
        logos like the Anthropic sunburst).
      • Image short side ≤ 300 px AND aspect > 2.5 (wide wordmarks like
        the arXiv, Mindgard Research, OpenAI typesettings).
      • PNG with > 40% fully-transparent pixels (typical of stamped logos
        with no background).
      • Color-poverty: ≤ 8 distinct quantized colors in a 64×64 thumbnail
        (logos almost always use 2-4 flat colors; real screenshots and
        diagrams have 30+ distinct colors after the same quantization).

    Intentionally conservative on the "real diagram / screenshot" side —
    if a screenshot has only flat UI chrome and a few colors it MIGHT trip
    the color-poverty signal, but those cases are rare and the fallback
    (Pexels b-roll) is still acceptable. False negatives (logos that slip
    through) are much worse than false positives.
    """
    if not path.exists():
        return False

    if _LOGO_NAME_RE.search(path.name):
        return True

    try:
        from PIL import Image  # local import keeps top-level cheap
    except Exception:
        return False

    try:
        with Image.open(path) as im:
            w, h = im.size
            short_side = min(w, h)
            aspect = w / h if h > 0 else 0

            # Square-ish logos (Anthropic sunburst, etc.).
            if short_side <= 600 and 0.5 <= aspect <= 2.0:
                return True

            # Wide wordmarks (arXiv 4:1, "MINDGARD RESEARCH", OpenAI
            # wordmarks, etc.). These are skinny-and-small; a wide
            # diagram or screenshot is much taller.
            if short_side <= 300 and aspect > 2.5:
                return True

            # Tall stacked logos (rare, but exist).
            if short_side <= 300 and aspect < 0.4:
                return True

            # Transparency-heavy stamps.
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA")
                rgba.thumbnail((256, 256))
                alphas = rgba.getchannel("A").getdata()
                total = len(alphas)
                if total > 0:
                    fully_transparent = sum(1 for a in alphas if a < 8)
                    if fully_transparent / total > 0.40:
                        return True

            # Color-poverty: only applied to small images. Logos use 2-6
            # flat colors; minimalist screenshots / paper figures CAN
            # have similar palettes but they tend to be much larger
            # (>800px short side). The combined signal "small AND
            # color-poor" is a strong logo indicator without flagging
            # legitimate diagrams.
            if short_side <= 800:
                thumb = im.convert("RGB").copy()
                thumb.thumbnail((64, 64))
                quantized: set[tuple[int, int, int]] = set()
                for r, g, b in thumb.getdata():
                    quantized.add((r // 32, g // 32, b // 32))
                    if len(quantized) > 10:
                        break  # early exit — definitely not a flat logo
                if len(quantized) <= 6:
                    return True
    except Exception as exc:
        log.debug("Logo heuristic failed for %s: %s", path, exc)

    return False


def _looks_like_decorative_illustration(path: Path) -> bool:
    """
    Heuristic: does this image look like an editorial illustration / hero
    artwork (the kind of stylized vector-y image news sites attach to
    articles for aesthetic) rather than a real screenshot, diagram, or
    photograph?

    Decorative illustrations are bad foreground material because they're
    generic — they don't carry the article's specific information the way
    a screenshot, paper figure, or photo does.

    Signal — combined dominant-color check on a 64×64 HSV thumbnail:

      • One quantized hue covers ≥ 35% of the image (flat-fill background
        — real photos basically never have this).
      • That dominant region has mean saturation ≥ 0.45 (vibrant fill,
        not a sky / neutral wall).
      • Mean saturation across the whole image ≥ 0.35 (overall
        oversaturated palette, classic "designer illustration" feel).

    All three signals together = illustration. Any one signal alone is
    not enough (a portrait against a blue sky might trigger #1 but not
    #2 + #3; a vibrant-but-realistic photo might trigger #3 but not
    #1).
    """
    if not path.exists():
        return False
    try:
        from PIL import Image  # local import keeps top-level cheap
    except Exception:
        return False

    try:
        with Image.open(path) as im:
            # Tiny thumbnail keeps this cheap. We sample ~4096 pixels.
            thumb = im.convert("RGB").copy()
            thumb.thumbnail((64, 64))
            hsv = thumb.convert("HSV")
            pixels = list(hsv.getdata())
            total = len(pixels)
            if total == 0:
                return False

            from collections import Counter

            # Quantize hue + value bucket so near-identical pixels group.
            buckets = Counter(
                (h // 16, s // 32, v // 32) for (h, s, v) in pixels
            )
            top_bucket, top_count = buckets.most_common(1)[0]
            top_share = top_count / total
            if top_share < 0.35:
                return False

            # Mean saturation of the dominant bucket and overall.
            top_sat = (top_bucket[1] * 32 + 16) / 255.0
            mean_sat = sum(s for (_, s, _) in pixels) / total / 255.0
            if top_sat < 0.45:
                return False
            if mean_sat < 0.35:
                return False

            return True
    except Exception as exc:
        log.debug("Illustration heuristic failed for %s: %s", path, exc)
        return False


def _block_logo_foregrounds(
    scenes: list[dict], out_dir: Path
) -> list[dict]:
    """
    Replace any scene's foreground `imageSrc` that looks like a logo OR a
    decorative editorial illustration with a Pexels b-roll clip. Falls
    back to leaving the scene alone only when Pexels is unavailable AND
    no alternative can be sourced. Logs every replacement so the user
    can audit which images got swapped.

    Phase D: every Pexels lookup carries the reel's running set of
    already-used Pexels paths so two scenes never get the same clip.
    The seed prefers the scene's own caption / headline / pane text so
    we don't fall back to "abstract ambient" (which previously caused
    two scenes to land on the same generic clip).
    """
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    try:
        from .media.pexels import search_video, search_photo  # type: ignore
    except Exception:
        search_video = None  # type: ignore
        search_photo = None  # type: ignore

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Fields the new scene catalog uses to point at primary visual content.
    # paper_walkthrough / paper_scroll are skipped — they always reference
    # the user's domain-specific paper figure, never a logo.
    PROTECTED_TYPES = {"paper_walkthrough", "paper_scroll"}
    MEDIA_FIELDS = (
        "imageSrc",
        "media_src",
        "window_src",
        "diagram_src",
        "top_media_src",
        "bottom_media_src",
        "article_src",
        "emotional_src",
    )

    used_pexels = _collect_pexels_paths_in_use(scenes)

    out: list[dict] = []
    for s in scenes:
        if s.get("type") in PROTECTED_TYPES:
            out.append(s)
            continue

        new_s = dict(s)
        replaced_any = False

        for field in MEDIA_FIELDS:
            src = s.get(field)
            if not src or not isinstance(src, str):
                continue
            if src.startswith("data:") or src.startswith("http"):
                continue
            path = Path(src)
            if not path.is_absolute():
                continue
            is_logo = _looks_like_logo(path)
            is_decorative = (not is_logo) and _looks_like_decorative_illustration(path)
            if not is_logo and not is_decorative:
                continue

            kind = "Logo-like" if is_logo else "Decorative-illustration"
            log.warning(
                "%s image detected as %s on scene %s; replacing.",
                kind, field, s.get("type"),
            )
            new_src: str | None = None
            if pexels_key and search_video is not None:
                # Compose a strong, scene-specific query: prefer the
                # scene's own copy + the consuming beat's pexels_query
                # if available; only fall back to "abstract ambient"
                # if neither exists.
                seed = _scene_pexels_seed(new_s) or "abstract ambient"
                try:
                    p = search_video(
                        seed, pexels_key, media_dir,
                        exclude_paths=used_pexels,
                    )
                    if p is None and search_photo is not None:
                        p = search_photo(
                            seed, pexels_key, media_dir,
                            exclude_paths=used_pexels,
                        )
                    if p is not None:
                        new_src = str(p)
                        used_pexels.add(p)
                except Exception as exc:
                    log.debug("Pexels lookup failed during logo swap: %s", exc)

            if new_src:
                new_s[field] = new_src
                log.info("  → swapped %s for Pexels: %s", field, Path(new_src).name)
            else:
                new_s.pop(field, None)
                log.warning("  → no Pexels fallback found; cleared %s", field)
            replaced_any = True

        out.append(new_s if replaced_any else s)

    return out


# ─── Cap consecutive Pexels-video runs ───────────────────────────────────────


_PEXELS_FILE_RE = re.compile(r"pexels[-_](photo|video)", re.IGNORECASE)


def _collect_unused_article_images(scenes: list[dict], out_dir: Path) -> list[Path]:
    """
    Build a queue of real article images (paper figures, sourced
    screenshots) that exist in media/ but are NOT currently referenced
    by any scene's `imageSrc` or `bg_media_src`. These are preferred
    over Pexels stock photos when we need to break up a long Pexels-video
    run, since the user wants more REAL content per reel.

    Pexels-named files (photo or video) are excluded — those are stock,
    not article content.
    """
    media_dir = out_dir / "media"
    if not media_dir.exists():
        return []
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    candidates: list[Path] = []
    for f in sorted(media_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in image_exts:
            continue
        if _PEXELS_FILE_RE.search(f.name):
            continue
        candidates.append(f)

    # Mark anything already referenced by a scene as used.
    used: set[str] = set()
    for s in scenes:
        for key in ("imageSrc", "bg_media_src", "bg_image"):
            v = s.get(key)
            if isinstance(v, str) and v.startswith("/"):
                used.add(str(Path(v).resolve()))
    return [p for p in candidates if str(p.resolve()) not in used]


def _cap_consecutive_pexels_videos(
    scenes: list[dict], out_dir: Path, *, max_run: int = 1
) -> list[dict]:
    """
    Walk the timeline and ensure no run of more than `max_run` consecutive
    "image" scenes use a Pexels VIDEO. With max_run=1, every Pexels video
    must be followed by something more substantial — preferably a real
    article image (paper figure, sourced screenshot), and only as a last
    resort a Pexels still photo.

    Replacement order:
      1. Unused real article media (preferred — more relevant content).
      2. Pexels still photo (fallback when no unused real media remains).

    Either replacement "resets" the run counter so we get the pattern
    [V][R][V][R][V][P][V][R]… where V=Pexels-video, R=real-article-image,
    P=Pexels-photo fallback.
    """
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    try:
        from .media.pexels import search_photo  # type: ignore
    except Exception:
        search_photo = None  # type: ignore

    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    real_pool = _collect_unused_article_images(scenes, out_dir)
    log.info(
        "Pexels-cap: %d unused real article image(s) available as preferred replacements",
        len(real_pool),
    )

    out: list[dict] = []
    run = 0
    for s in scenes:
        src = s.get("imageSrc") or ""
        is_pexels_video = (
            s.get("type") == "image" and bool(_PEXELS_VIDEO_RE.search(src))
        )
        if is_pexels_video:
            run += 1
            if run > max_run:
                replaced = False

                # 1. Try real article media first.
                if real_pool:
                    real = real_pool.pop(0)
                    new_s = dict(s)
                    new_s["imageSrc"] = str(real)
                    out.append(new_s)
                    log.info(
                        "Capped Pexels-video run (>%d): replaced with REAL article image %s",
                        max_run,
                        real.name,
                    )
                    run = 0
                    replaced = True

                # 2. Fall back to a Pexels still photo.
                if not replaced and pexels_key and search_photo is not None:
                    seed = (s.get("caption") or "abstract ambient").strip()
                    photo = None
                    try:
                        photo = search_photo(seed, pexels_key, media_dir)
                    except Exception as exc:
                        log.debug("search_photo failed during run cap: %s", exc)
                    if photo is not None:
                        new_s = dict(s)
                        new_s["imageSrc"] = str(photo)
                        out.append(new_s)
                        log.info(
                            "Capped Pexels-video run (>%d): replaced with Pexels photo %s",
                            max_run,
                            photo.name,
                        )
                        run = 0
                        replaced = True

                if replaced:
                    continue
                # Couldn't replace at all — fall through and keep the
                # original Pexels video. Cap will eventually reset on
                # the next non-Pexels scene.
        else:
            run = 0
        out.append(s)
    return out


# ─── Phase B post-LLM normalisations ─────────────────────────────────────────

# Scene types that the legacy prompt taught to emit a per-scene `keyword`
# pill (the small sticky pill that double-stamped the global subtitle).
# We retired keyword pills in Phase B — Python strips the field everywhere.
_SCENE_TYPES_WITH_LEGACY_KEYWORD = {
    "numbered_reveal",
    "floating_window",
    "split_screen",
}

# Hard cap on numbered_reveal.title length. The title pill is whiteSpace:nowrap
# and longer titles get the tail trimmed by the canvas edge (we saw "Decoder
# converts to pixels" lose the trailing "s" in the Phase A render).
_NUMBERED_REVEAL_TITLE_CAP = 22


def _strip_scene_keyword_fields(scenes: list[dict]) -> list[dict]:
    """Drop the legacy `keyword` field from any scene that still emits it.

    Keyword pills were retired in Phase B — every scene-level keyword pill
    was double-stamping the global PillCaption (which already shows the
    current word). The render pipeline still tolerates the field for
    back-compat with older scripts, but stripping it here keeps debug
    output and renders consistent.
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    stripped_total = 0
    for s in scenes:
        if s.get("type") in _SCENE_TYPES_WITH_LEGACY_KEYWORD and "keyword" in s:
            new_s = {k: v for k, v in s.items() if k != "keyword"}
            stripped_total += 1
            out.append(new_s)
        else:
            out.append(s)
    if stripped_total:
        log.info("Stripped legacy `keyword` field from %d scenes", stripped_total)
    return out


def _force_split_screen_horizontal(scenes: list[dict]) -> list[dict]:
    """Force every `split_screen` scene to orientation: horizontal.

    Vertical splits were retired in Phase B — they read poorly at 9:16 and
    confused the seam-tracking subtitle logic (the global pill rides the
    Y seam at y=960, which is irrelevant for an X-axis split). If the LLM
    still emits `vertical`, rewrite it to `horizontal` and flip the
    pane slide_from directions to a valid top/bottom pair.
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    fixed = 0
    for s in scenes:
        if s.get("type") != "split_screen":
            out.append(s)
            continue
        if (s.get("orientation") or "").lower() != "vertical":
            out.append(s)
            continue
        new_s = dict(s)
        new_s["orientation"] = "horizontal"
        # Re-stamp slide_from to a valid top/bottom pair. We don't know
        # which pane was previously "left" vs "right" — just give pane_a
        # "top" and pane_b "bottom" deterministically.
        for pane_key, direction in (("pane_a", "top"), ("pane_b", "bottom")):
            pane = new_s.get(pane_key)
            if isinstance(pane, dict):
                new_pane = dict(pane)
                new_pane["slide_from"] = direction
                new_s[pane_key] = new_pane
        out.append(new_s)
        fixed += 1
    if fixed:
        log.info("Rewrote %d vertical split_screen scenes to horizontal", fixed)
    return out


def _normalize_numbered_reveal(scenes: list[dict]) -> list[dict]:
    """Two normalisations for `numbered_reveal`:

      1. Global renumber: the circles get numbered 1..N across the reel
         in render order, regardless of what the LLM emitted. Stops the
         "two scenes both labelled 3" bug from the Phase A render.
      2. Title cap: hard-truncate titles longer than 22 chars and add an
         ellipsis. The render-side title pill is whiteSpace:nowrap.
    """
    if not scenes:
        return scenes
    counter = 0
    out: list[dict] = []
    capped_titles = 0
    for s in scenes:
        if s.get("type") != "numbered_reveal":
            out.append(s)
            continue
        counter += 1
        new_s = dict(s)
        new_s["number"] = counter
        title = (new_s.get("title") or "").strip()
        if len(title) > _NUMBERED_REVEAL_TITLE_CAP:
            # Trim on word boundary if possible, leaving room for an ellipsis.
            cap = _NUMBERED_REVEAL_TITLE_CAP - 1
            cut = title[:cap].rsplit(" ", 1)[0] or title[:cap]
            new_s["title"] = cut + "…"
            capped_titles += 1
        else:
            new_s["title"] = title
        out.append(new_s)
    if counter:
        log.info(
            "numbered_reveal: renumbered %d scenes 1..%d (capped %d titles)",
            counter,
            counter,
            capped_titles,
        )
    return out


def _normalize_comparison_scenes(scenes: list[dict]) -> list[dict]:
    """
    The `comparison` scene schema is strict (left/right brand+value blocks
    + a top title) but the LLM keeps emitting it with `left_label` /
    `right_label` / `shared_insight` instead. Rather than burn a whole
    render with a Zod failure, normalise any malformed comparison into
    a horizontal `split_screen` whose two text panes carry the two
    labels and whose subtitle text carries the shared insight.

    A well-formed comparison (both `left.brand` and `right.brand`) is
    passed through untouched.
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    converted = 0
    for s in scenes:
        if s.get("type") != "comparison":
            out.append(s)
            continue
        left = s.get("left")
        right = s.get("right")
        title = s.get("title")
        well_formed = (
            isinstance(left, dict) and left.get("brand")
            and isinstance(right, dict) and right.get("brand")
            and isinstance(title, str) and title.strip()
        )
        if well_formed:
            out.append(s)
            continue

        # Best-effort salvage: pull brand-ish fields from the LLM's
        # alternative shape and convert into a split_screen.
        left_label = (
            (left or {}).get("label") if isinstance(left, dict) else None
        ) or s.get("left_label") or s.get("a_label") or "Option A"
        right_label = (
            (right or {}).get("label") if isinstance(right, dict) else None
        ) or s.get("right_label") or s.get("b_label") or "Option B"
        insight = (
            s.get("shared_insight")
            or s.get("insight")
            or s.get("subtitle")
            or s.get("title")
            or ""
        ).strip()

        new_s: dict = {
            "type": "split_screen",
            "duration_sec": float(s.get("duration_sec") or 4.0),
            "orientation": "horizontal",
            "pane_a": {
                "kind": "text",
                "text": str(left_label),
                "slide_from": "top",
            },
            "pane_b": {
                "kind": "text",
                "text": str(right_label),
                "slide_from": "bottom",
            },
        }
        # Carry the shared insight as a top annotation if present.
        if insight:
            new_s["top_annotation"] = {
                "text": insight,
                "anchor": "above_block",
            }
        out.append(new_s)
        converted += 1

    if converted:
        log.info(
            "comparison: salvaged %d malformed scene(s) → split_screen", converted,
        )
    return out


def _resolve_headline_bg_conflicts(scenes: list[dict]) -> list[dict]:
    """When a headline scene has both `bg_image` and `bg_media_src`, drop
    the still — the video is the layer the renderer actually shows, and
    `bg_image` was sneaking through with the giant `paper-scroll.png`
    sometimes (15+ MB), which Remotion's static handler refuses to serve
    inside the bundled webpack environment, causing 404s mid-render.

    We always prefer `bg_media_src` over `bg_image` when both are set on
    a headline scene; the video already has a poster frame Remotion can
    use as a fallback if needed.
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    fixed = 0
    for s in scenes:
        if s.get("type") == "headline" and s.get("bg_image") and s.get("bg_media_src"):
            new_s = {k: v for k, v in s.items() if k != "bg_image"}
            fixed += 1
            out.append(new_s)
        else:
            out.append(s)
    if fixed:
        log.info(
            "headline-bg conflict: dropped redundant bg_image on %d scene(s)",
            fixed,
        )
    return out


def _strip_pipeline_highlight_bboxes(scenes: list[dict]) -> list[dict]:
    """Retire the legacy `highlights` bbox system on pipeline_highlight.

    The LLM was hallucinating bbox coordinates (it never sees the diagram
    image), so the highlight rectangles landed in random empty regions.
    Phase B replaces this with editorial top/bottom annotations rendered
    in the empty strips above/below the diagram.

    We strip `highlights` from the scene; the Remotion component will
    treat the absence of the field as "no highlights, render annotations
    only". Existing `top_annotation` / `bottom_annotation` fields pass
    through untouched.
    """
    if not scenes:
        return scenes
    out: list[dict] = []
    stripped = 0
    for s in scenes:
        if s.get("type") != "pipeline_highlight":
            out.append(s)
            continue
        if "highlights" not in s:
            out.append(s)
            continue
        new_s = {k: v for k, v in s.items() if k != "highlights"}
        stripped += 1
        out.append(new_s)
    if stripped:
        log.info("Dropped legacy `highlights` bboxes from %d pipeline scenes", stripped)
    return out


def _cap_dramatic_word(
    scenes: list[dict], vibe: dict | None
) -> list[dict]:
    """Cap `dramatic_word` usage to at most 1 per reel, vibe-gated.

    The vibe profile carries `allow_dramatic_word: bool`. When that flag
    is false (most vibes), every `dramatic_word` scene gets coerced into
    a `floating_window` with the dramatic word as its accent annotation
    — same beat slot, different visual treatment.

    When the flag is true (e.g. "Bold Statement" vibe), keep the FIRST
    `dramatic_word` and coerce any subsequent ones (because the user
    explicitly said at most one per reel).
    """
    if not scenes:
        return scenes
    allow = bool((vibe or {}).get("allow_dramatic_word", False))
    seen_keep = False
    out: list[dict] = []
    coerced = 0
    for s in scenes:
        if s.get("type") != "dramatic_word":
            out.append(s)
            continue
        if allow and not seen_keep:
            seen_keep = True
            out.append(s)
            continue
        # Coerce to floating_window with the dramatic word as a soft
        # annotation. We don't have a clean window_src on hand here, so
        # downgrade to a `headline` scene type with the word as the
        # primary text — guaranteed renderable, no broken media path.
        word = (s.get("word") or s.get("text") or "").strip()
        new_s = {
            "type": "headline",
            "duration_sec": s.get("duration_sec", 3.0),
            "kicker": "",
            "headline": word,
            "subhead": "",
        }
        # Preserve bg_media_src if the dramatic_word had one — gives the
        # downgraded headline scene a Pexels b-roll instead of plain bg.
        if "bg_media_src" in s:
            new_s["bg_media_src"] = s["bg_media_src"]
        out.append(new_s)
        coerced += 1
    if coerced:
        log.info(
            "dramatic_word capped (vibe.allow_dramatic_word=%s): coerced %d → headline",
            allow,
            coerced,
        )
    return out


# ─── Phase C: statement-mode timeline ───────────────────────────────────────


# Scene types where the avatar (host bust) is visible. When an active
# statement-mode beat lands on one of these, the overlay anchors top-right
# so it doesn't crash into the avatar's face/body (lower half of canvas).
_AVATAR_SCENE_TYPES = {"hook", "avatar_full"}

# Scene types whose hero media occupies the TOP half of the canvas. When
# a statement-mode beat lands on one of these, anchor bottom-left so the
# text doesn't overlap the diagram / paper / article screenshot.
_TOP_HEAVY_SCENE_TYPES = {
    "pipeline_highlight",
    "paper_walkthrough",
    "paper_scroll",
    "article_headline",
    "headline",
}


def _statement_anchor_for_scene(
    scene_type: str, vibe_default: str
) -> str:
    """Decide top_right vs bottom_left for one scene/beat.

    Per-scene overrides win over the vibe default:
      • Avatar visible           → top_right
      • Hero media on top half   → bottom_left
      • Otherwise                → vibe default
    """
    if scene_type in _AVATAR_SCENE_TYPES:
        return "top_right"
    if scene_type in _TOP_HEAVY_SCENE_TYPES:
        return "bottom_left"
    return vibe_default if vibe_default in ("top_right", "bottom_left") else "bottom_left"


def _build_statement_segments(
    *,
    beats: list[Beat],
    scenes: list[dict],
    word_timestamps: list[WordTimestamp],
    vibe: dict | None,
) -> list[dict]:
    """Build the StatementOverlay timeline for the reel.

    For every beat with `statement=True`, locate its word range in the
    voiceover and emit a segment {text, start, end, anchor}. The anchor
    comes from the vibe default with per-scene overrides (avatar →
    top_right, top-heavy hero → bottom_left).

    The scene type is identified by walking `scenes` left-to-right and
    consuming one beat per non-walkthrough scene (mirrors the assignment
    fix_scene_timing already does, just simplified for statement gating).
    """
    if not beats:
        return []

    vibe_default = "bottom_left"
    if isinstance(vibe, dict):
        anchor = vibe.get("statement_anchor")
        if anchor in ("top_right", "bottom_left"):
            vibe_default = anchor

    # Map beat_id → owning scene type (best-effort 1:1 walk; mirrors
    # fix_scene_timing's assignment but cheaper because we don't need to
    # rescale durations).
    beat_to_scene_type: dict[int, str] = {}
    beat_cursor = 0
    n_beats = len(beats)
    for scene in scenes:
        explicit = scene.get("_beat_ids") or []
        scene_type = scene.get("type", "")
        if explicit:
            for bid in explicit:
                if 0 <= bid < n_beats:
                    beat_to_scene_type[bid] = scene_type
        else:
            if beat_cursor < n_beats:
                beat_to_scene_type[beat_cursor] = scene_type
                beat_cursor += 1

    # StatementOverlay was designed for short punchlines (≤ ~10 words).
    # Anything longer wraps to many lines at the fixed 108 px size and
    # covers the canvas. Beats above this cap fall back to the normal
    # per-word PillCaption rendering, which handles arbitrary length.
    STATEMENT_MAX_WORDS = 14

    segments: list[dict] = []
    cursor = 0
    for beat in beats:
        if not beat.statement:
            continue
        words = beat.text.split()
        if len(words) > STATEMENT_MAX_WORDS:
            log.info(
                "Statement beat %d skipped (%d words > %d) — falling back to "
                "word-by-word caption: %r",
                beat.id,
                len(words),
                STATEMENT_MAX_WORDS,
                beat.text[:80],
            )
            continue
        match = _find_word_subsequence(word_timestamps, words, cursor)
        if match is None:
            log.warning(
                "Statement beat %d (%r) not found in word_timestamps — skipping",
                beat.id,
                beat.text[:60],
            )
            continue
        first_idx, last_idx = match
        cursor = last_idx + 1
        scene_type = beat_to_scene_type.get(beat.id, "")
        anchor = _statement_anchor_for_scene(scene_type, vibe_default)
        segments.append(
            {
                "text": beat.text.strip(),
                "start": float(word_timestamps[first_idx].start_sec),
                "end": float(word_timestamps[last_idx].end_sec),
                "anchor": anchor,
            }
        )
    return segments


# ─── Total-duration cap ──────────────────────────────────────────────────────


def _enforce_max_reel_duration(
    scenes: list[dict],
    *,
    target_sec: float = 85.0,
    max_sec: float = 89.0,
) -> list[dict]:
    """
    Two-tier duration enforcement:
      • If total > `max_sec` (89s): hard-trim all scenes proportionally so
        the reel fits the platform's 90s feed cap (Instagram Reels, TikTok).
      • If total is in (`target_sec`, `max_sec`]: log a warning but leave
        the timeline intact — the rhythm is more important than shaving
        2–3s here.
    Minimum per-scene duration is 0.6s so we don't strobe through 0.1s
    flashes after a heavy trim. Trim is proportional so relative pacing
    stays intact.
    """
    if not scenes:
        return scenes
    total = sum(float(s.get("duration_sec", 0)) for s in scenes)
    if total <= target_sec:
        return scenes
    if total <= max_sec:
        log.info(
            "Reel duration %.1fs is in [target=%.1fs, max=%.1fs] — leaving as-is",
            total,
            target_sec,
            max_sec,
        )
        return scenes
    factor = max_sec / total
    log.info(
        "Reel duration %.1fs > hard cap %.1fs — trimming all scenes by ×%.3f",
        total,
        max_sec,
        factor,
    )
    out: list[dict] = []
    for s in scenes:
        new_s = dict(s)
        scaled = float(s.get("duration_sec", 0)) * factor
        new_s["duration_sec"] = max(0.6, round(scaled, 2))
        out.append(new_s)
    return out
