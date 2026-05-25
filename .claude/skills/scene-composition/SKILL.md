---
name: scene-composition
description: Reference catalog of all 12 Remotion scene types with when-to-use, required fields, and visual character. Use this when picking the right scene for a content beat or when authoring a new scene's JSON entry.
---

# Scene Composition Reference

Every scene type in `video-types.ts`, with full prop reference and directorial intent.

## hook

**Use it for:** the first scene of every video. The single line that makes someone stop scrolling.

```json
{
  "type": "hook",
  "duration_sec": 4,
  "headline": "Anthropic built a cyberweapon. Then it leaked.",
  "accent_words": ["cyberweapon", "leaked"],
  "bg_image": "https://...",  // optional — strong visual context
  "tagline": "THE LINE BETWEEN SAFETY AND VULNERABILITY JUST GOT THINNER"  // optional
}
```

- 5–14 words for the headline. Anything longer dies on small screens.
- Pick 2–4 `accent_words` — these light up in the brand accent color.
- Skip `bg_image` if you have nothing good — `NoiseBackground` looks great alone.

## kinetic_type

**Use it for:** punch lines, hot takes, opinion statements that should feel like spoken-word emphasis. Text appears word-by-word with a spring punch.

```json
{
  "type": "kinetic_type",
  "duration_sec": 3,
  "text": "Models are eating software",
  "accent_words": ["eating"],
  "words_per_burst": 1
}
```

- Keep `text` to 4–8 words. Longer kills the kinetic feel.
- `words_per_burst` controls how many words land at once: `1` = staccato, `2` = phrase chunks, `3` = louder pace.
- Use sparingly — 1–2 per video at most. Overuse turns it into noise.

## broll_montage

**Use it for:** rapid image cycling. "Here are 5 of the new tools" / "all the models that broke this benchmark." Crucial for reactive density.

```json
{
  "type": "broll_montage",
  "duration_sec": 5,
  "images": ["url1", "url2", "url3", "url4"],
  "captions": ["GPT-4o", "Claude 3.5", "Gemini 2", "Llama 4"],
  "title": "MODELS COMPARED",   // optional pinned chip
  "frames_per_image": 24        // optional override (defaults to even split)
}
```

- 3–6 images per montage is the sweet spot. <3 looks sparse; >6 turns into a slideshow.
- `captions[i]` is shown over `images[i]` — leave entries empty (`""`) to skip a caption.
- `title` shows in the top-left throughout — use it as a category label (e.g. "OS COVERAGE", "TIMELINE").

## body

**Use it for:** the core fact / insight / explanation step. Vertical layout: image on top half, text on bottom half.

```json
{
  "type": "body",
  "duration_sec": 6,
  "lines": [
    "It's not that the model is malicious.",
    "It's that the reward was poorly specified.",
    "The agent did exactly what we asked."
  ],
  "image": "https://...",
  "arrows": [[0.3, 0.4, 0.6, 0.45]]  // optional [x1,y1,x2,y2] in 0-1 fractions
}
```

- 2–4 `lines`. The first line is auto-highlighted in accent color.
- Use `image` whenever you have a visually relevant one. Text-only `body` is fine but flatter.
- `arrows` rarely needed — only for "look at this thing here" moments.

## context

**Use it for:** source attribution, setting up "why this matters." Bottom-anchored text over a fullscreen image or video.

```json
{
  "type": "context",
  "duration_sec": 5,
  "lines": [
    "The breach happened through a third-party vendor.",
    "Bloomberg first reported the story Tuesday."
  ],
  "source_label": "BLOOMBERG",
  "source_image": "https://...",     // optional
  "source_video": "https://...mp4"   // optional, takes precedence over image
}
```

- Use `source_label` whenever the topic comes from a named publication.
- 2–3 `lines` — context should feel atmospheric, not informational.
- `source_video` is great for breaking news where there's a clip. Auto-played.

## compare

**Use it for:** A vs B comparisons. "What they said" vs "What they did". "Old approach" vs "New approach".

```json
{
  "type": "compare",
  "duration_sec": 7,
  "left_label": "GPT-4 Turbo",
  "left_points": ["128k context", "$10/1M input", "Slow"],
  "right_label": "GPT-4o",
  "right_points": ["128k context", "$5/1M input", "2x faster"]
}
```

- Each side: 2–4 `points`. Match the count between sides.
- Keep points short (3–6 words). They need to read fast.
- Right side is rendered with slightly muted color (the "challenger") — order matters.

## stat

**Use it for:** ONE killer number. Don't string two stats back-to-back.

```json
{
  "type": "stat",
  "duration_sec": 4,
  "number": 175,
  "prefix": "$",
  "suffix": "B",
  "label": "Saved per year by automation",
  "context_line": "Across the entire S&P 500"   // optional
}
```

- The number animates with a CountUp — end value drives drama.
- `prefix` / `suffix` examples: `"$"`, `"%"`, `"x"`, `"M"`, `"B"`, `"K"`.
- Use `context_line` to give the number meaning. Without it the stat is hollow.

## quote

**Use it for:** direct quoted speech with attribution. Always quoted and italicized in the render.

```json
{
  "type": "quote",
  "duration_sec": 5,
  "text": "We cannot let advanced capabilities exist without advanced safety.",
  "speaker": "Dario Amodei",
  "role": "CEO, Anthropic"
}
```

- The text typewriters in. Keep to one sentence — long quotes break the pacing.
- Always include `speaker` if you have it. Without attribution it's just an opinion.

## timeline

**Use it for:** chronological story unfolds. "Here's how this happened over time."

```json
{
  "type": "timeline",
  "duration_sec": 10,
  "title": "HOW IT UNFOLDED",
  "events": [
    {"date": "2024 Q3", "label": "Mythos project secretly approved"},
    {"date": "2025 Jan", "label": "Mercor breached"},
    {"date": "2025 Mar", "label": "Bloomberg breaks the story"}
  ]
}
```

- 3–5 events is ideal. Fewer feels thin; more crowds the frame.
- Keep `label` to <8 words. `date` can be a string in any format.
- Use `title` as a header chip (uppercase rendered).

## paper / paper_walkthrough

**Use it for:** research paper screenshot. Educational mode only.

```json
{
  "type": "paper_walkthrough",
  "imageSrc": "PAPER_SCROLL_IMAGE",
  "beat_ids": [2],
  "stops": [
    {"anchor_id": "title", "caption": "EquiSumm — Gender-aware summarization"}
  ]
}
```

**Length rules (Python enforces; do not exceed):**

| Paper beats in narrative | Plan | Total duration |
|---|---|---|
| 1 beat (≤ 6 s of voice) | **Single stop on the title anchor only.** Treat it as a flashed evidence shot. | ≤ 6 s |
| 2 beats | 2 stops — title plus the specific section the second beat names. | ≤ 10 s |
| 3+ beats, each citing a different section | Multi-stop walkthrough. | ≤ 14 s total, ≤ 4 s per stop |

**Hard rules:**
- Each stop's `dwell_sec` MUST equal the voice duration of its owning beat (Python computes from `word_timestamps`).
- Never use `paper_walkthrough` to fill time. If the narrative doesn't justify scrolling, drop the paper scene entirely and use `body`, `floating_window`, or `split_screen`.
- `imageSrc` is always `PAPER_SCROLL_IMAGE` (resolved by Python).
- `anchor_id` values come from the `PAPER_ANCHORS` block in the prompt.

The paper is supporting evidence, not the show. The voiceover is the show.

## web_scroll

**Use it for:** article screenshot scrolling. Cite the original story visually instead of just naming it.

```json
{
  "type": "web_scroll",
  "duration_sec": 7,
  "screenshot": "https://...techcrunch-article.png",
  "source_label": "techcrunch.com",
  "highlight_y": 800,
  "highlight_label": "The key claim"
}
```

- Different from `paper` in tone: web articles feel more reactive.
- `highlight_y` is the vertical pixel position of the region to highlight (in the original screenshot).

## outro

**Use it for:** the closing scene. Always last.

```json
{
  "type": "outro",
  "duration_sec": 3,
  "cta": "Follow for more AI drops.",
  "handle": "@yourhandle"   // optional, defaults to BRAND.accountHandle
}
```

- Keep `cta` to 5–7 words.
- `handle` overrides the default — only set it if multiple accounts are sharing this video.

## Cross-references

- Schema source of truth: `remotion_dev/src/video-types.ts`
- For pacing rules see: `pacing-rules.md`
- For media allocation see: `b-roll-orchestration.md`
