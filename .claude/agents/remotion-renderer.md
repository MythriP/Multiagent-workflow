---
name: remotion-renderer
description: TypeScript/React-based video rendering engine. Consumes `video_script.json` from `script-agent` and renders a 9:16 MP4 via Remotion. Owns the 12 scene templates, animation primitives, caption track, and SFX/audio mixing. Use when the user wants to add a new scene type, tweak motion, debug a render, or change brand styling.
model: claude-sonnet-4
tools: Read, Grep, Glob, Shell, Write, StrReplace
---

# Remotion Renderer

Lives at `remotion_dev/`. Pure rendering layer — no LLM calls.

## Inputs

- `video_script.json` from `script-agent` — passed via `--props` to `npx remotion render`.
- `voiceover.mp3` + word timestamps from `script-agent`.
- Media files (images, b-roll, lipsync clips) referenced by absolute path.

## Outputs

- `remotion_dev/outputs/videos/YYYY-MM-DD/HH-MM/<slug>/final.mp4`

## Source layout

- `src/Root.tsx` — composition registry.
- `src/DynamicReel.tsx` — top-level reel that walks the `scenes[]` array.
- `src/scenes/` — one component per scene type (hook, body, kinetic_type, broll_montage, context, etc.).
- `src/components/` — shared primitives (Caption, AvatarLipsync, AnimatedText).
- `src/animations/` — spring/interp helpers.
- `src/templates/` — text-post (carousel) templates.
- `src/brand.ts` — colors, fonts, sizing tokens.
- `src/video-types.ts` — **schema source of truth** for `video_script.json`.

## Run

```bash
cd remotion_dev
npm install
npm run dev                                # studio at http://localhost:3000
npx ts-node scripts/render-video.ts path/to/video_script.json
```

## Contract changes

Any change to `src/video-types.ts` MUST be reflected in `script_agent/scene_writer.py` and the **scene-composition** skill.
