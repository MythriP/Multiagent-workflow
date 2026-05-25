---
name: video-director
description: Master skill for composing a Remotion `video_script.json` from a sourced `topic.json`. Use this when the script_agent needs to translate raw topic material into a directed video script with the right scene mix, pacing, and visual treatment for the Pinch ML/AI content brand.
---

# Video Director Skill

You are the director of every video produced by this pipeline. Your output is a `video_script.json` matching the schema in `remotion_dev/src/video-types.ts`. The video must match the energy of Varun Mayya, 100xEngineers, and Riley Brown — not a static slideshow.

## The brand at a glance

- **Format:** 9:16 vertical (1080×1920) — Reels / TikTok / YouTube Shorts
- **Voice:** punchy, opinionated, ML-educator energy
- **Two content modes:**
  - `reactive` (60%): "X just dropped", "Y was leaked", "Z said this" — fast cuts, hot-take energy
  - `educational` (40%): "Here's how X works", "Why Y matters" — structured beats, more breathing room

The mode is set by `topic.json["content_type"]`. Use it to drive every directorial choice below.

## The 12 scene types and when to use each

Map content beats → scenes. This table is the ground truth.

| Scene type | Use it when... | Typical duration |
|---|---|---|
| `hook` | Opening line. Always scene #1. Big headline, optional bg image. | 3–5 sec |
| `kinetic_type` | Hot-take statement, opinion line, punchy money-line. Word-by-word kinetic typography. | 2–4 sec |
| `broll_montage` | "Here are the X tools / models / examples" — rapid image cycling, ~0.6–1.0s per image. | 4–8 sec |
| `body` | The core fact/insight. 2–4 lines + an image (now image-on-top, text-on-bottom for vertical). | 4–8 sec |
| `context` | Source attribution + setup ("Bloomberg reports that..."). Bottom-anchored over image/video. | 4–6 sec |
| `compare` | A vs B, before vs after, what-they-said vs what-they-did. | 5–8 sec |
| `stat` | One dominant number with a label and context line. | 3–5 sec |
| `quote` | Direct pull quote with speaker attribution. | 4–6 sec |
| `timeline` | Sequence of dated events ("Here's how it unfolded"). | 8–12 sec |
| `paper` | Research paper / arXiv screenshot scrolling. Educational only. | 7–10 sec |
| `web_scroll` | Article screenshot scrolling, with optional highlight callout. | 5–8 sec |
| `outro` | Always scene last. Handle + CTA. | 2–3 sec |

## Scene mix recipes

### Reactive video (15–25 sec total)
A typical reactive video: **6–8 scenes**, fast cuts.

```
1. hook         (3-4s)   — the headline
2. kinetic_type (2-3s)   — the punch line / hot take
3. context      (4-5s)   — source attribution
4. broll_montage(4-5s)   — visuals from topic.json["media"]["images"]
5. stat OR compare (3-5s)— the killer fact
6. body         (3-5s)   — what it means
7. outro        (2-3s)
```

### Educational video (30–60 sec total)
A typical educational deep-dive: **8–12 scenes**, more dwell time.

```
1. hook         (4-5s)   — the question / promise
2. context      (5-6s)   — why this matters
3. body         (6-8s)   — concept #1
4. paper OR web_scroll (7-9s) — show the source material
5. body         (6-8s)   — concept #2
6. compare      (6-8s)   — old vs new approach (when relevant)
7. stat         (3-5s)   — one quantifying number
8. body         (5-7s)   — concept #3
9. quote        (5-6s)   — expert opinion (when available)
10. outro       (2-3s)
```

## Allocating media from topic.json

`topic.json["media"]["images"]` arrives as an ordered list (most relevant first). Distribute as follows:

- **First image** → `hook` scene's `bg_image` (it sets the visual identity)
- **Next 3–5 images** → either:
  - `broll_montage.images` (reactive mode — high visual density)
  - `body.image` per scene (educational mode — one strong image per concept)
- **Article screenshot** (when present) → `web_scroll.screenshot`
- **Paper PDF screenshot** (when present, educational) → `paper.paper_image`
- **Videos** (`media.videos`) → `context.source_video` for the context-setting scene
- **Never repeat an image** within the same video — each shot must be visually distinct

## Word_timestamps + captions

The voiceover pipeline returns `word_timestamps` from ElevenLabs. Always set `show_captions: true` (default). The `CaptionTrack` overlay then renders word-by-word highlighted captions at the bottom — this is the single biggest factor matching reactive-creator energy. Only set `show_captions: false` for completely silent videos.

## Common mistakes to avoid

- ❌ Don't open with `context` — always `hook` first.
- ❌ Don't string 3+ `body` scenes back-to-back — break them up with `stat`, `quote`, `kinetic_type`, or `broll_montage`.
- ❌ Don't use `paper` in reactive videos — it kills momentum.
- ❌ Don't use `kinetic_type` for full sentences — keep it to 4–8 words max.
- ❌ Don't allocate more than 1 image per `body` scene — extras are wasted.
- ❌ Don't end without `outro` — the handle + CTA is non-negotiable.

## Output format

Return a complete `video_script.json` matching `videoScriptSchema`. The total scene `duration_sec` should sum to the target video length (15–25s reactive, 30–60s educational). When `word_timestamps` is provided, double-check that `duration_sec` per scene aligns with the word boundaries returned by ElevenLabs — `script_agent/scene_writer.py::fix_scene_timing` does this; trust it.

## Cross-references

- Schema: `remotion_dev/src/video-types.ts`
- See also: `scene-composition.md`, `b-roll-orchestration.md`, `pacing-rules.md`, `caption-styling.md`
