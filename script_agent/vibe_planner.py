# ─── vibe_planner.py ────────────────────────────────────────────────────────
# Step 0 of the visual pipeline: pick ONE named "vibe" from a curated
# catalog and pipe it through the downstream pipeline.
#
# Phase B locks the vibe system to a small curated catalog. The LLM no
# longer composes a palette + motion + font from scratch — instead it
# reads the topic / narration and chooses the single best-fit vibe name.
# This guarantees palette harmony, font cohesion, and consistent motion
# treatment per reel. (Phase A's free-form composition kept producing
# unaesthetic color combinations and a different "feel" every reel.)
#
# Each vibe in the catalog carries:
#   - color_palette (primary_bg, secondary_bg, accent, text_primary)
#   - motion_intensity ("calm" | "balanced" | "kinetic")
#   - font_style ("editorial" | "neutral-sans" | "kinetic-sans" | "mono-tech")
#   - hook_variant ("split_50_50" | "reactive_creator")
#   - allow_dramatic_word (bool — only ONE vibe in the catalog allows it)
#   - dot_grid_enabled (bool — VibeBackdrop dot grid)
#   - scene_pattern_bias  (LLM hint, not a hard constraint)
#   - video_gen_modifiers (appended to every Veo prompt)
#   - ambient_backdrop_queries (Pexels fallback queries)
#
# The vibe NEVER edits the narration. Visual-only.

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import call_claude
from .paths import PROMPTS_DIR

log = logging.getLogger(__name__)


# ─── Curated vibe catalog ────────────────────────────────────────────────────
# Five hand-tuned visual profiles. Each one is internally cohesive —
# colors pulled from the same accent family, font + motion picked to
# match the editorial tone. The vibe planner picks one of these names
# and the rest of the pipeline reads from the entry directly.

VIBE_CATALOG: dict[str, dict[str, Any]] = {
    "clean_tech_serious": {
        "vibe_name": "clean_tech_serious",
        "tone_summary": (
            "Sober, technical, confident — research breakdown energy. "
            "Black canvas, cool indigo accent, dense editorial typography."
        ),
        "color_palette": {
            "primary_bg": "#0A0A0A",
            "secondary_bg": "#141414",
            "accent": "#8B7FFF",
            "text_primary": "#FFFFFF",
        },
        "motion_intensity": "balanced",
        "font_style": "editorial",
        "hook_variant": "split_50_50",
        "allow_dramatic_word": False,
        "dot_grid_enabled": True,
        "statement_anchor": "top_right",
        "video_gen_modifiers": [
            "cinematic 35mm, shallow depth of field",
            "soft directional key light, near-black backdrop",
            "muted desaturated palette, high contrast",
        ],
        "scene_pattern_bias": {
            "split_screen": 0.7,
            "pipeline_highlight": 0.7,
            "floating_window": 0.6,
            "numbered_reveal": 0.4,
            "article_headline": 0.5,
        },
        "ambient_backdrop_queries": [
            "abstract dark texture slow motion",
            "out of focus city lights night",
        ],
    },
    "bold_statement": {
        "vibe_name": "bold_statement",
        "tone_summary": (
            "Provocative hot-take energy — single declarative sentences "
            "rendered in heavy editorial type over deep oxblood + cream. "
            "Only vibe that allows dramatic_word."
        ),
        "color_palette": {
            "primary_bg": "#2A0F12",
            "secondary_bg": "#3A1A1F",
            "accent": "#F4E1C1",
            "text_primary": "#FFF3E0",
        },
        "motion_intensity": "balanced",
        "font_style": "editorial",
        "hook_variant": "split_50_50",
        "allow_dramatic_word": True,
        "dot_grid_enabled": False,
        "statement_anchor": "bottom_left",
        "video_gen_modifiers": [
            "cinematic anamorphic, warm tungsten light",
            "deep red-brown shadows, cream highlights",
            "shallow depth of field, slow push-in",
        ],
        "scene_pattern_bias": {
            "split_screen": 0.9,
            "pipeline_highlight": 0.3,
            "floating_window": 0.5,
            "numbered_reveal": 0.3,
            "article_headline": 0.7,
        },
        "ambient_backdrop_queries": [
            "moody red brown out of focus",
            "warm bokeh deep shadow",
        ],
    },
    "reactive_creator": {
        "vibe_name": "reactive_creator",
        "tone_summary": (
            "Creator-led, social-feed energy — warm off-white canvas, "
            "coral accent, near-black type. Reads like a YouTube "
            "thumbnail. Fast, kinetic, friendly."
        ),
        "color_palette": {
            "primary_bg": "#F4ECE2",
            "secondary_bg": "#E6DCD0",
            "accent": "#FF4D3D",
            "text_primary": "#16110D",
        },
        "motion_intensity": "kinetic",
        "font_style": "kinetic-sans",
        "hook_variant": "reactive_creator",
        "allow_dramatic_word": False,
        "dot_grid_enabled": False,
        "statement_anchor": "bottom_left",
        "video_gen_modifiers": [
            "natural daylight, warm tones",
            "shallow depth of field, handheld feel",
            "slight film grain, lived-in textures",
        ],
        "scene_pattern_bias": {
            "split_screen": 0.7,
            "pipeline_highlight": 0.4,
            "floating_window": 0.7,
            "numbered_reveal": 0.5,
            "article_headline": 0.8,
        },
        "ambient_backdrop_queries": [
            "warm sunlit bokeh slow",
            "out of focus coffee shop window",
        ],
    },
    "moody_archive": {
        "vibe_name": "moody_archive",
        "tone_summary": (
            "Slow, cinematic, retrospective — navy canvas, amber accent, "
            "cream type. History / retrospective / philosophical content."
        ),
        "color_palette": {
            "primary_bg": "#0B1A2C",
            "secondary_bg": "#13263F",
            "accent": "#E8B96B",
            "text_primary": "#F4EAD5",
        },
        "motion_intensity": "calm",
        "font_style": "editorial",
        "hook_variant": "reactive_creator",
        "allow_dramatic_word": False,
        "dot_grid_enabled": False,
        "statement_anchor": "bottom_left",
        "video_gen_modifiers": [
            "cinematic 35mm grain, slow pan",
            "amber tungsten + cool ambient mix",
            "deep navy shadows, golden highlights",
        ],
        "scene_pattern_bias": {
            "split_screen": 0.6,
            "pipeline_highlight": 0.4,
            "floating_window": 0.7,
            "numbered_reveal": 0.4,
            "article_headline": 0.8,
        },
        "ambient_backdrop_queries": [
            "old archive footage grain blue",
            "library window dust particles",
        ],
    },
    "terminal_green": {
        "vibe_name": "terminal_green",
        "tone_summary": (
            "Cyberpunk / hacker aesthetic — near-black canvas, phosphor "
            "green accent, monospaced type. AI safety, security, "
            "low-level systems."
        ),
        "color_palette": {
            "primary_bg": "#060A07",
            "secondary_bg": "#0E1410",
            "accent": "#39FF8A",
            "text_primary": "#E8F5E9",
        },
        "motion_intensity": "kinetic",
        "font_style": "mono-tech",
        "hook_variant": "reactive_creator",
        "allow_dramatic_word": False,
        "dot_grid_enabled": True,
        "statement_anchor": "top_right",
        "video_gen_modifiers": [
            "fluorescent green rim light, black backdrop",
            "high contrast cyberpunk, scanlines",
            "fast camera moves, neon highlights",
        ],
        "scene_pattern_bias": {
            "split_screen": 0.6,
            "pipeline_highlight": 0.8,
            "floating_window": 0.6,
            "numbered_reveal": 0.5,
            "article_headline": 0.5,
        },
        "ambient_backdrop_queries": [
            "green code matrix scrolling",
            "abstract neon network nodes",
        ],
    },
}

# Canonical default if the planner fails entirely.
_DEFAULT_VIBE_NAME = "clean_tech_serious"


@dataclass
class VibeProfile:
    """In-memory representation of vibe.json so callers can introspect easily."""

    vibe_name: str
    tone_summary: str
    color_palette: dict[str, str]
    motion_intensity: str           # "calm" | "balanced" | "kinetic"
    font_style: str                 # "editorial" | "neutral-sans" | "kinetic-sans" | "mono-tech"
    hook_variant: str               # "split_50_50" | "reactive_creator"
    allow_dramatic_word: bool
    dot_grid_enabled: bool
    statement_anchor: str           # "top_right" | "bottom_left" (Phase C)
    video_gen_modifiers: list[str]
    scene_pattern_bias: dict[str, float]
    ambient_backdrop_queries: list[str]
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vibe_name": self.vibe_name,
            "tone_summary": self.tone_summary,
            "color_palette": self.color_palette,
            "motion_intensity": self.motion_intensity,
            "font_style": self.font_style,
            "hook_variant": self.hook_variant,
            "allow_dramatic_word": self.allow_dramatic_word,
            "dot_grid_enabled": self.dot_grid_enabled,
            "statement_anchor": self.statement_anchor,
            "video_gen_modifiers": self.video_gen_modifiers,
            "scene_pattern_bias": self.scene_pattern_bias,
            "ambient_backdrop_queries": self.ambient_backdrop_queries,
        }


def _profile_from_catalog_entry(entry: dict[str, Any]) -> VibeProfile:
    return VibeProfile(
        vibe_name=entry["vibe_name"],
        tone_summary=entry["tone_summary"],
        color_palette=dict(entry["color_palette"]),
        motion_intensity=entry["motion_intensity"],
        font_style=entry["font_style"],
        hook_variant=entry["hook_variant"],
        allow_dramatic_word=bool(entry["allow_dramatic_word"]),
        dot_grid_enabled=bool(entry["dot_grid_enabled"]),
        statement_anchor=entry.get("statement_anchor", "bottom_left"),
        video_gen_modifiers=list(entry["video_gen_modifiers"]),
        scene_pattern_bias=dict(entry["scene_pattern_bias"]),
        ambient_backdrop_queries=list(entry["ambient_backdrop_queries"]),
        raw=dict(entry),
    )


# ─── Catalog selection ───────────────────────────────────────────────────────


def _coerce_to_catalog_name(payload: Any) -> str:
    """Extract a catalog vibe name from whatever the LLM emitted.

    Accepts either a bare string ("bold_statement"), a JSON object with a
    `vibe_name` field, or just any string we can normalise. Falls back to
    the default vibe if nothing matches.
    """
    candidate: str | None = None
    if isinstance(payload, str):
        candidate = payload
    elif isinstance(payload, dict):
        raw_name = payload.get("vibe_name") or payload.get("name")
        if isinstance(raw_name, str):
            candidate = raw_name
    if not candidate:
        return _DEFAULT_VIBE_NAME
    normalized = candidate.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in VIBE_CATALOG:
        return normalized
    # Try a loose substring match (e.g. "boldStatement" → "bold_statement").
    for key in VIBE_CATALOG:
        if key in normalized or normalized in key:
            return key
    log.warning(
        "Vibe planner returned unknown name %r — falling back to %s",
        candidate,
        _DEFAULT_VIBE_NAME,
    )
    return _DEFAULT_VIBE_NAME


def _load_prompt() -> str:
    p = PROMPTS_DIR / "vibe-planner.md"
    if not p.exists():
        raise FileNotFoundError(f"vibe_planner prompt missing: {p}")
    return p.read_text()


def _catalog_summary_for_prompt() -> str:
    """Render the catalog into a compact string for the LLM prompt."""
    lines = ["AVAILABLE VIBES (pick exactly ONE):"]
    for name, entry in VIBE_CATALOG.items():
        lines.append(f"  • {name}: {entry['tone_summary']}")
    return "\n".join(lines)


def _build_user_message(narrative: str, topic: dict) -> str:
    title = topic.get("topic", "Unknown")
    slug = topic.get("slug", "")
    content_type = topic.get("content_type", "unknown")
    key_facts = topic.get("key_facts") or []
    sources = topic.get("sources") or []

    parts: list[str] = []
    parts.append(_catalog_summary_for_prompt())
    parts.append("")
    parts.append(f"TOPIC: {title}")
    parts.append(f"SLUG:  {slug}")
    parts.append(f"CONTENT TYPE: {content_type}")
    parts.append("")

    if key_facts:
        parts.append("KEY FACTS:")
        for fact in key_facts[:6]:
            clean = str(fact).strip()
            if clean:
                parts.append(f"  - {clean[:180]}")
        parts.append("")

    for src in sources[:2]:
        name = src.get("name", "Source")
        text = (src.get("text") or "").strip()
        if text:
            parts.append(f"SOURCE ({name}):")
            parts.append(text[:1200])
            parts.append("")

    parts.append("FINAL NARRATION (visual-only decisions; do NOT modify):")
    parts.append(narrative.strip())
    parts.append("")
    parts.append(
        'Reply with EXACTLY: {"vibe_name": "<one of the catalog names above>"}.'
        " No commentary, no fences."
    )
    return "\n".join(parts)


# ─── Public entry point ───────────────────────────────────────────────────────

def plan_vibe(
    *,
    narrative: str,
    topic: dict,
    out_dir: Path,
    anthropic_api_key: str,
    openai_api_key: str,
    model: str,
    claude_mode: str = "openai",
) -> VibeProfile:
    """
    Run the vibe planner. Always returns a usable VibeProfile, even if the
    LLM call fails — falls back to the default catalog entry.

    Phase B: the LLM only picks a NAME from the curated catalog. All
    visual attributes (palette, fonts, motion, hook variant, etc.) are
    looked up from the catalog by that name. No free composition.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    chosen_name = _DEFAULT_VIBE_NAME
    try:
        system_prompt = _load_prompt()
        user_message = _build_user_message(narrative, topic)
        log.info("🎨 Vibe planner: picking from catalog (mode=%s)...", claude_mode)
        raw = call_claude(
            label="vibe_planner",
            system=system_prompt,
            user=user_message,
            out_dir=out_dir,
            model=model,
            max_tokens=400,
            mode=claude_mode,
            anthropic_api_key=anthropic_api_key,
            openai_api_key=openai_api_key,
            expect_json=True,
        )
        # Tolerant parsing: accept raw JSON, a bare quoted string, or even
        # plaintext "bold_statement" with no JSON wrapper.
        payload: Any
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        chosen_name = _coerce_to_catalog_name(payload)
    except Exception as exc:
        log.exception("Vibe planner errored (%s) — using default vibe", exc)
        chosen_name = _DEFAULT_VIBE_NAME

    entry = VIBE_CATALOG[chosen_name]

    # Persist for downstream consumers
    vibe_path = out_dir / "vibe.json"
    vibe_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False))
    log.info(
        "✅ Vibe: %s | motion=%s | font=%s | hook=%s | dramatic_word=%s | accent=%s",
        entry["vibe_name"],
        entry["motion_intensity"],
        entry["font_style"],
        entry["hook_variant"],
        entry["allow_dramatic_word"],
        entry["color_palette"]["accent"],
    )

    return _profile_from_catalog_entry(entry)


def load_vibe(out_dir: Path) -> VibeProfile | None:
    """Load a previously-saved vibe.json. Returns None if absent/invalid.

    If the on-disk vibe has a name that matches a catalog entry, we
    return the catalog entry verbatim (so any post-Phase-B catalog
    updates flow through automatically). Otherwise the file's
    attributes are reused as-is to preserve historical reproducibility.
    """
    p = out_dir / "vibe.json"
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return None
    if isinstance(payload, dict):
        name = (payload.get("vibe_name") or "").strip()
        if name in VIBE_CATALOG:
            return _profile_from_catalog_entry(VIBE_CATALOG[name])
        # Legacy / pre-catalog file — best-effort load with defaults
        # backfilling missing Phase B fields.
        merged = dict(VIBE_CATALOG[_DEFAULT_VIBE_NAME])
        merged.update(payload)
        return _profile_from_catalog_entry(merged)
    return _profile_from_catalog_entry(VIBE_CATALOG[_DEFAULT_VIBE_NAME])
