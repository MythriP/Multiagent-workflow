---
name: caption-styling
description: How and when to enable word-by-word voiceover captions. Use when setting `show_captions` on `video_script.json` or tuning the global caption track.
---

# Caption Styling

Word-by-word synced captions are the single biggest reason reactive creators (Varun Mayya, 100xEngineers, Riley Brown) feel high-energy. The eye locks onto the highlighted word, the brain follows the audio. Without captions, retention plummets.

This skill covers when to use them, when to skip, and how to tune.

## How they work

`CaptionTrack` is a global overlay rendered above all scenes in `AnimatedVideo`. It reads `script.word_timestamps` (provided by ElevenLabs) and:

1. Groups words into **phrase chunks** of `BRAND.caption.maxWordsPerLine` (default: 4 words).
2. Shows the active chunk near the bottom of the frame, in a rounded dark pill.
3. Highlights the currently-spoken word in `accent_color` with a slight scale punch.
4. Fades chunks in/out over ~180ms at chunk boundaries.

It only renders when **both** of these are true:
- `script.show_captions` is `true` (default)
- `script.word_timestamps.length > 0`

## When to enable (default: ON)

Always enable captions when:

- ✅ The script has voiceover (ElevenLabs provided word_timestamps)
- ✅ The video is destined for Reels / TikTok / Shorts (people watch with sound off)
- ✅ Reactive content with quick cuts — captions ground the viewer

## When to disable

Set `show_captions: false` only when:

- The video is **completely silent** (no voiceover) — captions need word_timestamps to do anything anyway
- The video is a **typography-driven** piece where on-scene text already carries the words (e.g., 100% kinetic_type scenes — captions would compete)
- A specific platform (LinkedIn, Twitter) renders better without burned-in captions

If unsure, leave it on. The cost of showing captions when they're slightly redundant is low; the cost of NOT showing them when they would have helped is high.

## Tuning the appearance

Caption styling lives in `BRAND.caption` in `brand.ts`:

```ts
caption: {
  bottomOffset: 280,    // px from bottom — sits above platform UI safe-zone
  maxWordsPerLine: 4,   // words shown at once
  paddingX: 60,
  paddingY: 14,
  backgroundColor: "rgba(0,0,0,0.78)",
  borderRadius: 12,
}
```

### Common tweaks

| Goal | Change |
|---|---|
| Captions feel cramped → | increase `maxWordsPerLine` to 5 (only if voiceover is fast) |
| Captions overlap visual elements at bottom → | increase `bottomOffset` to 350+ |
| Captions feel too dim → | reduce backgroundColor opacity to `0.65` |
| Captions feel too in-your-face → | bump opacity to `0.85` |
| Captions feel too tall on screen → | reduce `BRAND.fontSize.caption` from 56 to 48 |

## Color logic

The CaptionTrack uses three colors per word:

- **Active word** (currently being spoken): `accent_color` from the script (per-video accent)
- **Past words** in the current chunk: `BRAND.textPrimary` (white)
- **Future words** in the current chunk: `BRAND.textDim` (35% white)

The active word also gets a soft glow (`0 0 18px ${accentColor}55`) for emphasis.

**Don't** override per-scene — captions should feel global, not per-scene branded.

## Common mistakes

- ❌ Setting `show_captions: false` for a video that has voiceover. Always enable for voiceover content.
- ❌ Rendering captions over a kinetic_type scene where the same text is already centered. Either skip captions in that scene (out of scope for now — it's all-or-nothing) OR don't use both.
- ❌ Cranking `maxWordsPerLine` past 6. Becomes unreadable on phone screens.
- ❌ Setting `bottomOffset` to 0. Platform UI (Like/Comment/Share buttons on TikTok) covers the bottom ~180px.

## Word-timestamp accuracy

ElevenLabs returns timestamps with sub-100ms precision. The CaptionTrack handles this internally:

- Lookahead window: `start_sec - 0.05` (50ms early) so the word appears just before being spoken
- Lookafter window: `end_sec + 0.05` (50ms late) so it stays highlighted briefly

If the captions visibly drift from the audio, the issue is upstream (in `voiceover.py`'s timestamp parsing), not in this overlay.

## Cross-references

- Component: `remotion_dev/src/animations/CaptionTrack.tsx`
- Schema: `remotion_dev/src/video-types.ts` (look for `show_captions` and `word_timestamps`)
- For voiceover pipeline: `script_agent/voiceover.py`
