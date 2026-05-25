# ─── narrative.py ─────────────────────────────────────────────────────────────
# Claude call #1: topic.json + media inventory → narrative text + beat plan.
#
# The narrative is the voiceover script ElevenLabs will speak.
# The beat plan tells us what to show visually during each voice chunk,
# including which images to use and whether to generate new ones.

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .media import MediaResult, build_media_inventory_text, execute_beat_media, process_media
from .llm import call_claude
from .paths import PROMPTS_DIR

log = logging.getLogger(__name__)


# Emoji / pictograph code-point ranges. Locked 2026-05-13: the reel's visual
# language is flat, confident, editorial — emojis read as social-media filler
# and clash with the typography. This regex covers the standard Unicode emoji
# blocks plus the variation selector and zero-width joiner that appear inside
# compound emojis (e.g. family-of-three glyphs).
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F6FF"  # symbols, pictographs, transport
    "\U0001F700-\U0001F77F"  # alchemical
    "\U0001F780-\U0001F7FF"  # geometric shapes ext
    "\U0001F800-\U0001F8FF"  # supplemental arrows-C
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols & pictographs ext-A
    "\U0001F1E0-\U0001F1FF"  # regional indicator (flags)
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0000FE0F"             # variation selector-16
    "\U0000200D"             # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    """Remove emoji glyphs from any narrative or beat text and collapse the
    leftover whitespace. Called on every monologue, beat, and cached
    narrative before it leaves narrative.py."""
    if not text:
        return text
    stripped = _EMOJI_RE.sub("", text)
    # Collapse runs of whitespace introduced by removed glyphs, but preserve
    # paragraph breaks (the LLM uses double-newlines as beat separators).
    stripped = re.sub(r"[ \t]+", " ", stripped)
    stripped = re.sub(r" *\n *", "\n", stripped)
    return stripped.strip()

# Slug-keyed narrative cache. The user explicitly approved the narrations
# from these snapshot runs, so subsequent renders for these topics reuse
# the EXACT prose + beat plan from the cached run instead of re-calling
# Claude (which produces a slightly different narrative each time and
# breaks the user's "I loved that narration" approval).
#
# Each value points to a directory containing `narrative.txt` and
# `narrative_raw.json` — the canonical artifacts written by a successful
# `generate_narrative` run.
_SCRIPT_OUTPUTS_ROOT = (
    Path(__file__).resolve().parent / "outputs"
)
_NARRATIVE_CACHE: dict[str, Path] = {
    "researchers-gaslit-claude-into-giving":
        _SCRIPT_OUTPUTS_ROOT / "2026-05-07" / "05-28"
        / "researchers-gaslit-claude-into-giving",
    "memorai-memory-organization-retrieval-adaptive":
        _SCRIPT_OUTPUTS_ROOT / "2026-05-07" / "05-31"
        / "memorai-memory-organization-retrieval-adaptive",
}


def _load_cached_narrative(slug: str) -> tuple[str, dict] | None:
    """
    If `slug` is in the approved-narrative cache AND the snapshot dir
    still has both `narrative.txt` and `narrative_raw.json`, return
    (narrative_text, parsed_raw_json). Otherwise return None.
    """
    snapshot = _NARRATIVE_CACHE.get(slug)
    if snapshot is None:
        return None
    txt_path = snapshot / "narrative.txt"
    raw_path = snapshot / "narrative_raw.json"
    if not txt_path.exists() or not raw_path.exists():
        log.warning(
            "Narrative cache miss for slug=%s: snapshot dir %s missing artifacts",
            slug, snapshot,
        )
        return None
    try:
        narrative_text = txt_path.read_text().strip()
        parsed = json.loads(raw_path.read_text())
    except Exception as exc:
        log.warning("Failed to load cached narrative for slug=%s: %s", slug, exc)
        return None
    return narrative_text, parsed


@dataclass
class Beat:
    id: int
    text: str                        # verbatim from narrative
    beat_type: str                   # hook / context / fact / demo / stat / paper / article / compare / quote / timeline / montage / punch / cta
    needs_generated_image: bool = False
    generate_prompt: str | None = None
    preferred_media_url: str | None = None
    needs_video_clip: bool = False
    video_url: str | None = None
    # LLM hints for trimming the demo clip to the relevant moment.
    # Both are interpreted as seconds inside the source video. Either may be
    # None, in which case the renderer falls back to playing from the start.
    video_start_hint_sec: float | None = None
    video_end_hint_sec: float | None = None
    # Extra media URLs for montage beats (rendered as broll_montage scenes).
    # Order is preserved — first URL appears first in the cycle.
    extra_media_urls: list[str] = field(default_factory=list)
    # Pexels stock query (2-4 word visual phrase) and stock kind ("video"/"photo").
    # Used by the media resolver to fetch ambient back-layer footage.
    pexels_query: str | None = None
    stock_kind: str = "video"
    # Populated after media execution:
    media_path: Path | None = None
    extra_media_paths: list[Path] = field(default_factory=list)
    pexels_path: Path | None = None
    pexels_is_video: bool = False
    # Phase C: when true, this beat's narration text is rendered by the
    # global StatementOverlay (whole-phrase, big bold) and the per-word
    # PillCaption is suppressed for the beat's duration. The narrative
    # LLM nominates candidates; Python enforces ≤2 statement beats per
    # reel (excluding hook/cta which have their own treatments).
    statement: bool = False


@dataclass
class NarrativeResult:
    narrative: str                   # full voiceover text (with [pause] markers)
    beats: list[Beat]
    media: MediaResult
    out_dir: Path


def _enforce_statement_cap(beats: list["Beat"], *, max_count: int = 2) -> None:
    """In-place: keep at most `max_count` beats with `statement=True`.

    Hook + CTA beats can never carry the statement flag (they have their
    own dedicated scene types). Beyond the cap, statement=True is reset
    to False on the longest / latest beats so the surviving statements
    feel intentional rather than spammed.
    """
    # Hook + CTA never qualify regardless of LLM nomination.
    for b in beats:
        if b.beat_type in ("hook", "cta") and b.statement:
            b.statement = False

    nominated = [b for b in beats if b.statement]
    if len(nominated) <= max_count:
        if nominated:
            log.info(
                "Statement beats (%d/%d): %s",
                len(nominated),
                max_count,
                [b.id for b in nominated],
            )
        return

    # Prefer earlier + shorter beats — they tend to be the actual punchlines
    # rather than lengthy context that the LLM mis-tagged.
    nominated_sorted = sorted(
        nominated,
        key=lambda b: (len(b.text.split()), b.id),
    )
    keep_ids = {b.id for b in nominated_sorted[:max_count]}
    dropped = []
    for b in beats:
        if b.statement and b.id not in keep_ids:
            b.statement = False
            dropped.append(b.id)
    log.info(
        "Statement cap: kept %s, dropped %s (max=%d/reel)",
        sorted(keep_ids),
        dropped,
        max_count,
    )


def _load_freeform_prompt() -> str:
    """Pass-1 prompt: voice rules + 7 training narrations as few-shot."""
    p = PROMPTS_DIR / "narrative-freeform.md"
    if p.exists():
        return p.read_text()
    return (PROMPTS_DIR / "narrative.md").read_text()


def _load_critic_prompt() -> str:
    """Pass-1.5 prompt: evaluates the monologue and returns PASS or IMPROVE."""
    p = PROMPTS_DIR / "narrative-critic.md"
    if p.exists():
        return p.read_text()
    return ""


def _load_beats_prompt() -> str:
    """Pass-2 prompt: monologue → beat JSON."""
    p = PROMPTS_DIR / "narrative-beats.md"
    if p.exists():
        return p.read_text()
    return (PROMPTS_DIR / "narrative.md").read_text()


def _build_topic_context(topic: dict, media_result: MediaResult) -> str:
    """
    Shared topic context block fed to BOTH passes. Pass 1 uses it for grounding
    facts; pass 2 uses it for media selection.
    """
    parts: list[str] = []

    parts.append(f"TOPIC: {topic.get('topic', 'Unknown')}")
    parts.append(f"SLUG: {topic.get('slug', '')}")
    parts.append(f"CONTENT TYPE: {topic.get('content_type', 'unknown')}")
    parts.append(f"SCORE: {topic.get('score', 0)}")
    parts.append("")

    key_facts = topic.get("key_facts", [])
    if key_facts:
        parts.append("KEY FACTS (from enrichment):")
        for fact in key_facts[:8]:
            clean = fact.strip()
            if clean:
                parts.append(f"  • {clean[:200]}")
        parts.append("")

    sources = topic.get("sources", [])
    for src in sources[:2]:
        name = src.get("name", "Source")
        text = src.get("text", "")
        if text:
            parts.append(f"SOURCE ({name}):")
            parts.append(text[:1500])
            parts.append("")

    return "\n".join(parts)


def _build_freeform_user_message(topic: dict, media_result: MediaResult) -> str:
    """Pass-1 user message: ask the LLM to write the freeform monologue."""
    parts = [_build_topic_context(topic, media_result)]
    feedback = (topic.get("_redo_feedback") or "").strip()
    if feedback:
        parts.append(
            f"USER FEEDBACK ON THE PREVIOUS VERSION:\n{feedback}\n\n"
            "Please address this feedback in the new narration. Keep everything "
            "else that was working well."
        )
        parts.append("")
    parts.append(
        "Write a 120–280 word voiceover monologue for this topic following the "
        "voice rules in your system prompt. Plain prose only — no JSON, no "
        "markdown headings. Match the cadence of the reference examples."
    )
    return "\n".join(parts)


def _build_improve_user_message(
    topic: dict, media_result: MediaResult, monologue: str, critique: str
) -> str:
    """Pass-1b user message: first draft + critique → improved monologue."""
    parts = [_build_topic_context(topic, media_result)]
    parts.append("FIRST DRAFT (your previous monologue):")
    parts.append(monologue.strip())
    parts.append("")
    parts.append("CRITIQUE (specific lines flagged by the editor):")
    parts.append(critique.strip())
    parts.append("")
    parts.append(
        "Rewrite ONLY the flagged lines. Keep all other sentences exactly as "
        "written. Return the full monologue as plain prose — no JSON, no headings, "
        "no commentary. Do not add new content; do not remove unflagged sentences."
    )
    return "\n".join(parts)


def _build_beats_user_message(
    topic: dict, media_result: MediaResult, monologue: str
) -> str:
    """Pass-2 user message: monologue + media inventory → beat JSON."""
    parts = [_build_topic_context(topic, media_result)]
    parts.append("MONOLOGUE (verbatim — segment this into beats):")
    parts.append(monologue.strip())
    parts.append("")
    parts.append(build_media_inventory_text(media_result))
    parts.append("")
    parts.append(
        "Return JSON with `narrative` (the monologue verbatim) and `beats` "
        "(visual segmentation), per the schema in your system prompt."
    )
    return "\n".join(parts)


def generate_narrative(
    topic: dict,
    out_dir: Path,
    anthropic_api_key: str,
    openai_api_key: str,
    narrative_model: str,
    max_video_sec: int = 600,
    claude_mode: str = "openai",
    prev_monologue: Optional[Path] = None,
) -> NarrativeResult:
    """
    Two-pass narrative pipeline:
      0. Process media from topic.json (download images, get video metadata).
      1. PASS 1 — freeform monologue. The model writes pure prose using the
         7 training narrations as few-shot grounding. No JSON, no beat
         constraints, no media awareness.
      2. PASS 2 — beat segmentation. The model takes the monologue + media
         inventory and emits the existing beat JSON, anchoring each beat
         to a verbatim contiguous substring of the monologue.
      3. Execute media requests (generate images, download clips).
      4. Return NarrativeResult.
    Two passes is a deliberate split: when the LLM has to "write for slots"
    in one shot, every sentence is sized to fit a beat, which is the
    structural reason the output has historically read AI-flavoured. Letting
    pass 1 write monologue-first, pass 2 stage-second gives a far more
    creator-voiced result.
    """
    log.info("━━ Narrative: processing media...")
    media_result = process_media(topic, out_dir, openai_api_key, max_video_sec=max_video_sec)

    slug = topic.get("slug", "")
    cached = _load_cached_narrative(slug)

    if cached is not None:
        # User-approved narrative for this slug. Skip Claude pass 1 + 2
        # entirely and reuse the canonical text + beats. We still execute
        # the media plan below so per-beat Pexels/AI media gets fetched
        # into THIS run's media dir.
        narrative_text, parsed = cached
        narrative_text = _strip_emojis(narrative_text)
        log.info(
            "✨ Reusing approved narrative for slug=%s (%d words) — skipping Claude passes",
            slug, len(narrative_text.split()),
        )
        # Mirror the cached artifacts into the current out_dir so debug
        # introspection still works for this run.
        (out_dir / "narrative_monologue.txt").write_text(narrative_text + "\n")
        (out_dir / "narrative_raw.json").write_text(json.dumps(parsed, indent=2))
        # Pull beats out of the cached parsed JSON. If `narrative` field
        # exists in parsed JSON, prefer that as the canonical text.
        narrative_text = (parsed.get("narrative") or narrative_text).strip()
        raw_beats: list[dict] = parsed.get("beats", [])
    else:
        # ── PASS 1 — freeform monologue (or reuse prev for 'scenes' stage) ──────
        freeform_system = _load_freeform_prompt()

        if prev_monologue is not None and prev_monologue.exists():
            monologue = prev_monologue.read_text().strip()
            log.info(
                "♻️  Reusing existing monologue from %s (%d words) — skipping pass 1 + critic",
                prev_monologue, len(monologue.split()),
            )
            (out_dir / "narrative_monologue.txt").write_text(monologue + "\n")
        else:
            log.info("━━ Narrative pass 1 (freeform monologue, mode=%s)...", claude_mode)
            freeform_user = _build_freeform_user_message(topic, media_result)

            monologue = call_claude(
                label="narrative_freeform",
                system=freeform_system,
                user=freeform_user,
                out_dir=out_dir,
                model=narrative_model,
                max_tokens=2000,
                mode=claude_mode,
                anthropic_api_key=anthropic_api_key,
                openai_api_key=openai_api_key,
                expect_json=False,
            )
            monologue = _strip_emojis((monologue or "").strip())
            if not monologue:
                raise RuntimeError("Pass 1 returned an empty monologue")
            (out_dir / "narrative_monologue.txt").write_text(monologue + "\n")
            log.info("✅ Pass 1: %d words", len(monologue.split()))

        # ── PASS 1.5 — critic evaluation (skipped when reusing prev monologue) ──
        critic_system = _load_critic_prompt()
        if critic_system and prev_monologue is None:
            log.info("━━ Narrative pass 1.5 (critic evaluation)...")
            critic_result = call_claude(
                label="narrative_critic",
                system=critic_system,
                user=f"MONOLOGUE TO EVALUATE:\n\n{monologue}",
                out_dir=out_dir,
                model=narrative_model,
                max_tokens=1000,
                mode=claude_mode,
                anthropic_api_key=anthropic_api_key,
                openai_api_key=openai_api_key,
                expect_json=False,
            )
            critic_result = (critic_result or "").strip()
            (out_dir / "narrative_critique.txt").write_text(critic_result + "\n")

            if critic_result.startswith("PASS"):
                log.info("✅ Critic: PASS — monologue approved, no changes needed")
            else:
                log.info("📝 Critic: IMPROVE — running improvement pass...")
                log.debug("Critique:\n%s", critic_result)
                improve_user = _build_improve_user_message(
                    topic, media_result, monologue, critic_result
                )
                improved = call_claude(
                    label="narrative_freeform_improved",
                    system=freeform_system,
                    user=improve_user,
                    out_dir=out_dir,
                    model=narrative_model,
                    max_tokens=2000,
                    mode=claude_mode,
                    anthropic_api_key=anthropic_api_key,
                    openai_api_key=openai_api_key,
                    expect_json=False,
                )
                improved = _strip_emojis((improved or "").strip())
                if improved:
                    monologue = improved
                    (out_dir / "narrative_monologue.txt").write_text(monologue + "\n")
                    log.info("✅ Improvement pass: %d words", len(monologue.split()))
                else:
                    log.warning("Improvement pass returned empty — keeping original monologue")
        else:
            log.info("⚠️  Critic prompt not found (.claude/prompts/narrative-critic.md missing) — skipping")

        # ── PASS 2 — beat segmentation ───────────────────────────────────────
        log.info("━━ Narrative pass 2 (beat segmentation)...")
        beats_system = _load_beats_prompt()
        beats_user = _build_beats_user_message(topic, media_result, monologue)

        raw = call_claude(
            label="narrative",
            system=beats_system,
            user=beats_user,
            out_dir=out_dir,
            model=narrative_model,
            max_tokens=16000,
            mode=claude_mode,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key,
            expect_json=True,
        )

        (out_dir / "narrative_raw.json").write_text(raw)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("Pass 2 returned invalid JSON: %s", exc)
            log.error("Raw response:\n%s", raw[:500])
            raise

        # Pass 2 should echo the monologue back in `narrative`. If it didn't,
        # fall back to the canonical pass-1 monologue so ElevenLabs gets the
        # right text.
        narrative_text: str = _strip_emojis(
            (parsed.get("narrative") or "").strip() or monologue
        )
        raw_beats: list[dict] = parsed.get("beats", [])

    # Validate / normalise beats
    beats: list[Beat] = []
    for b in raw_beats:
        extra_urls = b.get("extra_media_urls") or []
        if not isinstance(extra_urls, list):
            extra_urls = []
        def _opt_float(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        beats.append(
            Beat(
                id=b.get("id", len(beats)),
                text=_strip_emojis(b.get("text", "")),
                beat_type=b.get("beat_type", "fact"),
                needs_generated_image=bool(b.get("needs_generated_image")),
                generate_prompt=b.get("generate_prompt"),
                preferred_media_url=b.get("preferred_media_url"),
                needs_video_clip=bool(b.get("needs_video_clip")),
                video_url=b.get("video_url"),
                video_start_hint_sec=_opt_float(b.get("video_start_hint_sec")),
                video_end_hint_sec=_opt_float(b.get("video_end_hint_sec")),
                extra_media_urls=[u for u in extra_urls if isinstance(u, str)],
                pexels_query=(b.get("pexels_query") or "").strip() or None,
                stock_kind=(b.get("stock_kind") or "video").lower(),
                statement=bool(b.get("statement")),
            )
        )

    # Cap statement beats at 2 per reel. The LLM occasionally tags
    # everything as "statement"; the cap keeps the treatment rare and
    # therefore impactful. Hook + CTA beats are auto-excluded since
    # they have their own scene types and treatments.
    _enforce_statement_cap(beats, max_count=2)

    log.info("✅ Narrative: %d words, %d beats", len(narrative_text.split()), len(beats))
    log.info("   Beats: %s", [b.beat_type for b in beats])

    # Save narrative text for reference / ElevenLabs
    narrative_clean = narrative_text.replace("[pause]", " ").strip()
    (out_dir / "narrative.txt").write_text(narrative_text + "\n")

    # ── Execute media plan ────────────────────────────────────────────────────
    log.info("━━ Narrative: executing media plan...")
    beat_dicts = [
        {
            "id": b.id,
            "text": b.text,
            "needs_generated_image": b.needs_generated_image,
            "generate_prompt": b.generate_prompt,
            "preferred_media_url": b.preferred_media_url,
            "needs_video_clip": b.needs_video_clip,
            "video_url": b.video_url,
            "extra_media_urls": b.extra_media_urls,
            "pexels_query": b.pexels_query,
            "stock_kind": b.stock_kind,
        }
        for b in beats
    ]
    media_result = execute_beat_media(
        beat_dicts, media_result, out_dir, openai_api_key, max_video_sec=max_video_sec
    )

    # Attach media paths to Beat objects
    for beat in beats:
        beat.media_path = media_result.beat_media.get(beat.id)
        beat.extra_media_paths = media_result.beat_extra_media.get(beat.id, [])
        beat.pexels_path = media_result.beat_pexels.get(beat.id)
        beat.pexels_is_video = bool(media_result.beat_pexels_is_video.get(beat.id, False))

    return NarrativeResult(
        narrative=narrative_text,
        beats=beats,
        media=media_result,
        out_dir=out_dir,
    )
