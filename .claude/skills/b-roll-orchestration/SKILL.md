---
name: b-roll-orchestration
description: How to allocate the images and videos from `topic.json["media"]` across scenes for maximum visual impact. Use when composing scenes that need visual content sourced from the topic's raw materials.
---

# B-Roll Orchestration

Reactive creators (Varun Mayya, 100xEngineers) succeed because **something visual changes every 2–3 seconds**. This skill is how to allocate `topic.json["media"]` across the script so the video never feels static.

## What you're given

`topic.json["media"]` arrives like this:

```json
{
  "images": [
    "https://og-image-from-article.jpg",
    "https://twitter-screenshot.jpg",
    "https://product-screenshot.jpg",
    "https://chart-from-paper.jpg"
  ],
  "videos": [
    "https://youtube-embed.mp4"
  ]
}
```

Images are ordered by relevance (sourcing_agent does the ranking — the first image is usually the article's OG image, then secondary visuals). Videos are rare but high-value when present.

## Allocation strategy by content_type

### Reactive videos — VISUAL DENSITY IS EVERYTHING

Total scenes: 6–8. Target: every scene has visual movement.

| Scene | Media usage |
|---|---|
| `hook` | First image as `bg_image` (sets the visual identity) |
| `kinetic_type` | No media (pure typography) |
| `context` | Video if present → `source_video`; else `source_image` |
| `broll_montage` | Images 2–5 cycled rapidly (4 images at ~0.6s each = 2.4s + transitions = ~3s) |
| `stat` / `compare` | No media (data/comparison-driven) |
| `body` | Either image 6 (if available) OR text-only |
| `web_scroll` | Use only if you have a clean article screenshot — otherwise skip |
| `outro` | No media |

**Rule:** if `media.images` has fewer than 3, skip the `broll_montage` and use `body` scenes with `image` instead. Don't pad montages with weak images.

### Educational videos — ONE STRONG IMAGE PER CONCEPT

Total scenes: 8–12. Target: each `body` scene has one carefully chosen image that visually anchors that concept.

| Scene | Media usage |
|---|---|
| `hook` | First image as `bg_image` (with dark overlay applied) |
| `context` | First image OR same as hook |
| `body` × N | Distribute remaining images, one per body scene |
| `paper` | If `topic.json` has a paper PDF screenshot → use it here |
| `web_scroll` | If there's an article screenshot worth showing → use it here |
| `compare` | No media |
| `stat` / `quote` | No media |
| `outro` | No media |

**Rule:** if `media.images` has fewer than `body` scenes, leave the later `body` scenes text-only — don't reuse images.

## Image quality filtering (do this FIRST)

Before allocating, eliminate weak images:

- **Skip** logos, icons, favicons (usually < 200×200 pixels in the ranked list)
- **Skip** generic stock photos that don't relate to the topic
- **Skip** images smaller than 600×400 px
- **Skip** images that are mostly text (legibility kills at video scale)
- **Prefer** screenshots, product photos, charts, faces, real-world scenes

If after filtering you're left with <3 strong images, drop the `broll_montage` scene entirely. A bad montage is worse than no montage.

## Captions on broll_montage

The `captions` array on `broll_montage` is one-line-per-image. Use it to:

- Label the entity in the image: "GPT-4o", "Claude 3.5", "Llama 4"
- Label a moment: "Day 1", "Day 30", "Day 90"
- Skip with empty string `""` when the image speaks for itself

When all 4 images are visually obvious (e.g. faces, products), `captions` can be omitted entirely.

## Title chip on broll_montage

The `title` prop pins a chip to the top-left throughout the montage. Use it to:

- Categorize: "MODELS COMPARED", "TIMELINE", "EXAMPLES"
- Set context: "FROM THE PAPER", "USERS REACTED"

If the montage is short (3–4 images, <3 sec), skip the title — it's clutter.

## Special case: when there's a video

`media.videos` is rare. When present, the video almost always comes from a tweet, YouTube clip, or product demo. It is high-signal — give it pride of place:

- Use it on the `context` scene as `source_video` (autoplays as background).
- DO NOT also use a `source_image` on the same context — pick one.
- If it's a long video, the scene only shows the first few seconds. Pick a context scene duration that matches the visual interest of those seconds.

## Special case: paper / arXiv content

Educational topics often have a paper screenshot in `media.images`. You'll usually find it as a tall portrait screenshot (height > 1.5× width). When detected:

- Don't use it in `broll_montage` (won't crop well)
- Don't use it as `body.image` (the body image is rendered in the top half — text won't be readable)
- Do use it as `paper.paper_image` in a dedicated `paper` scene

## Cross-references

- Schema: `remotion_dev/src/video-types.ts`
- For scene definitions: `scene-composition.md`
- For pacing decisions: `pacing-rules.md`
