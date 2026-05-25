---
name: script-agent
description: Turns a sourced `topic.json` into a fully rendered 9:16 vertical video. Generates narration with Claude, voiceover with ElevenLabs, scene plans with Claude + Veo/Pexels b-roll, optional avatar lipsync with fal.ai, and renders the final MP4 via Remotion. Use whenever the user wants to produce a video from an existing topic or watch the sourcing queue for new ones.
model: claude-opus-4
tools: Read, Grep, Glob, Shell, Write, StrReplace
---

# Script Agent

The production agent. Consumes a `topic.json` and produces a finished video.

## Pipeline (in order)

1. **vibe planner** (`vibe_planner.py`) — picks tonal direction (reactive vs educational variants) from topic content.
2. **narrative** (`narrative.py`) — two-pass writer+critic loop produces the 120–280 word voiceover monologue plus structured beats. Uses prompts in `.claude/prompts/`.
3. **voiceover** (`media/voiceover.py`) — ElevenLabs TTS → `voiceover.mp3` + word-level timestamps.
4. **scene_writer** (`scene_writer.py`) — composes the Remotion `video_script.json` (12 scene types). Calls Pexels, fal.ai image gen, and Veo 3.1 Fast for b-roll.
5. **lipsync** (`media/lipsync.py`, optional) — per-segment talking-avatar clips via fal.ai.
6. **render** (`render.py`) — invokes `remotion_dev/scripts/render-video.ts` to produce the final MP4.

## Run modes

```bash
python -m script_agent.run --topic path/to/topic.json     # full pipeline
python -m script_agent.run --topic ... --resume scenes    # reuse narrative+voiceover
python -m script_agent.run --topic ... --resume render    # reuse video_script.json
python -m script_agent.run --watch                        # watch sourcing_agent/outputs/
```

`SKIP_VOICEOVER=true` (default in dev) renders silent with synthetic word timings.

## Outputs

`script_agent/outputs/YYYY-MM-DD/HH-MM/<slug>/` contains:
- `narrative.txt`, `narrative_monologue.txt`, `narrative_critique.txt`
- `voiceover.mp3`, `word_timestamps.json`
- `video_script.json` — Remotion input
- `final.mp4` — rendered video

## Skills this agent invokes

- **video-director** — orchestrates the whole `topic.json → video_script.json` translation. Load first.
- **scene-composition** — catalog of 12 scene types.
- **pacing-rules** — duration tables per scene + content_type.
- **b-roll-orchestration** — how to allocate `topic.media[]` across scenes.
- **caption-styling** — when to enable word-by-word captions.
- **narration-voice** — voice rules used by the narrative writer (pass 1).
- **narration-critic** — evaluation rules used by the narrative critic (pass 2).
- **video-prompt** — cinematic prompt engineering for Veo / Kling / Sora b-roll.

## Prompts loaded at runtime

All prompts live in `.claude/prompts/`:
- `narrative.md`, `narrative-beats.md`, `narrative-freeform.md` — narrative writer.
- `narrative-critic.md` — narrative critic.
- `scene-writer.md` — scene_writer pass.
- `vibe-planner.md` — vibe planner pass.

Resolution is done by `script_agent.paths.PROMPTS_DIR`.

## Contracts

**Input** (`topic.json`): see `sourcing-agent.md`.
**Output** (`video_script.json`): schema lives in `remotion_dev/src/video-types.ts`.
