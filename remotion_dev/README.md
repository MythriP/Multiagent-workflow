# remotion_dev — rendering engine

Pure TypeScript/React rendering layer. No LLM calls. Consumes `video_script.json` from `script_agent` and produces a 9:16 MP4.

## Source layout

```
remotion_dev/
├── package.json
├── tsconfig.json
├── remotion.config.ts
├── eslint.config.mjs
├── src/
│   ├── Root.tsx                 # composition registry
│   ├── DynamicReel.tsx          # top-level reel; walks scenes[]
│   ├── video-types.ts           # SCHEMA SOURCE OF TRUTH for video_script.json
│   ├── brand.ts                 # color, font, sizing tokens
│   ├── scenes/                  # one component per scene type
│   ├── components/              # shared primitives (Caption, AvatarLipsync, …)
│   ├── animations/              # spring/interp helpers
│   ├── templates/               # static text-post (carousel) templates
│   └── index.{ts,css}
├── scripts/
│   ├── render-video.ts          # CLI render entry (invoked by script_agent)
│   ├── render-post.ts           # text-post carousel render
│   └── types.ts
├── public/                      # static assets referenced by compositions
│   ├── avatar/                  # avatar-source.png, headshot.png, lipsync clips (cache)
│   ├── brand/  sfx/  images/  clips/  voiceovers/  audio/
└── outputs/
    ├── textposts/<date>/...
    └── videos/<date>/<time>/<slug>/final.mp4
```

## Commands

```bash
npm install
npm run dev                                              # studio at http://localhost:3000
npx ts-node scripts/render-video.ts path/to/video_script.json
```

## Contract

Any change to `src/video-types.ts` MUST be reflected in `script_agent/scene_writer.py` and the `scene-composition` skill (`.claude/skills/scene-composition/SKILL.md`).

## Outputs

Renders go to `outputs/videos/YYYY-MM-DD/HH-MM/<slug>/final.mp4`. This folder is gitignored and pruned aggressively — keep only the latest dated subfolder.
