# script_agent

Turns a sourced `topic.json` into a fully rendered 9:16 vertical video.

## Pipeline

```
topic.json
   │
   ▼  vibe_planner.py        ── Claude picks tonal direction (reactive vs educational)
   │
   ▼  narrative.py           ── two-pass writer + critic, produces voiceover script + beats
   │
   ▼  media/voiceover.py     ── ElevenLabs TTS → voiceover.mp3 + word_timestamps.json
   │
   ▼  scene_writer.py        ── Claude composes video_script.json
   │     ├── media/pexels.py     stock b-roll search
   │     ├── media/fal_image.py  photoreal image generation
   │     └── media/video_gen.py  Veo 3.1 Fast text-to-video
   │
   ▼  media/lipsync.py       ── (optional) fal.ai talking-avatar segments
   │
   ▼  render.py              ── invokes remotion_dev/scripts/render-video.ts
   │     └── media/sfx.py        SFX cue building
   │
   ▼
final.mp4
```

## Package layout

```
script_agent/
├── __init__.py
├── __main__.py              # `python -m script_agent`
├── pyproject.toml
├── paths.py                 # shared PROMPTS_DIR resolver → ../.claude/prompts
├── run.py                   # entry point (also `script-agent` console script)
├── vibe_planner.py
├── narrative.py
├── scene_writer.py
├── render.py
├── llm.py                   # Claude wrapper
└── media/
    ├── __init__.py
    ├── core.py              # MediaResult + per-beat orchestration
    ├── pexels.py
    ├── fal_image.py
    ├── video_gen.py
    ├── voiceover.py
    ├── lipsync.py
    └── sfx.py
```

## Install

```bash
pip install -e .
```

## Run

```bash
# Full pipeline
python -m script_agent --topic path/to/topic.json

# Resume from a later stage (reuses earlier outputs)
python -m script_agent --topic ... --resume narrative   # redo voiceover + scenes + render
python -m script_agent --topic ... --resume scenes      # redo scenes + render
python -m script_agent --topic ... --resume render      # render only

# Watch sourcing_agent/outputs/ and process new topics as they arrive
python -m script_agent --watch
```

`SKIP_VOICEOVER=true` (default during dev) renders silent with synthetic timings to avoid burning ElevenLabs credits.

## Output

```
script_agent/outputs/YYYY-MM-DD/HH-MM/<slug>/
├── narrative.txt
├── narrative_monologue.txt
├── narrative_critique.txt        # critic feedback if pass-1 failed
├── voiceover.mp3
├── word_timestamps.json
├── video_script.json             # Remotion input
├── media/                        # downloaded + generated assets
└── final.mp4
```

## Prompts

All LLM prompts live in `../.claude/prompts/` and are resolved through `script_agent.paths.PROMPTS_DIR`:

- `vibe-planner.md`
- `narrative.md`, `narrative-beats.md`, `narrative-freeform.md`
- `narrative-critic.md`
- `scene-writer.md`

## Skills

The agent harness in `../.claude/skills/` provides Claude with:

- `video-director` — orchestration master skill (load first)
- `scene-composition` — catalog of 12 Remotion scene types
- `pacing-rules` — duration tables per scene + content type
- `b-roll-orchestration` — how to allocate topic.media[] across scenes
- `caption-styling` — when to enable word-by-word captions
- `narration-voice` — voice rules for the writer pass
- `narration-critic` — evaluation rules for the critic pass
- `video-prompt` — Veo / Kling / Sora prompt engineering
