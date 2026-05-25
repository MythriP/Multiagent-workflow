---
name: pacing-rules
description: Duration tables and scene-pacing rules for reactive vs educational videos. Use this when setting `duration_sec` per scene or deciding total video length.
---

# Pacing Rules

The reference creators (Varun Mayya, 100xEngineers, Riley Brown) hit very specific pacing targets. Drift away from these and the video starts to feel like a slideshow.

## Total video duration targets

| Content type | Target length | Hard cap |
|---|---|---|
| Reactive (breaking news, drops) | **18–25 sec** | 30 sec |
| Educational (deep-dive explainers) | **35–55 sec** | 75 sec |

**Why:** TikTok/Reels/Shorts retention drops sharply after 30s for reactive content. Educational content earns more dwell time but only up to ~60s before completion rate craters.

## Per-scene duration cheatsheet

### Reactive mode (avg 2.5 sec per scene)

| Scene type | Min | Sweet spot | Max |
|---|---|---|---|
| `hook` | 3 | 4 | 5 |
| `kinetic_type` | 2 | 2.5 | 3 |
| `broll_montage` | 4 | 5 | 7 |
| `body` | 3 | 4 | 5 |
| `context` | 4 | 5 | 6 |
| `stat` | 3 | 3.5 | 5 |
| `compare` | 5 | 6 | 7 |
| `quote` | 4 | 5 | 6 |
| `outro` | 2 | 2.5 | 3 |

### Educational mode (avg 4.5 sec per scene)

| Scene type | Min | Sweet spot | Max |
|---|---|---|---|
| `hook` | 4 | 5 | 6 |
| `context` | 5 | 6 | 7 |
| `body` | 6 | 7 | 9 |
| `paper` | 7 | 9 | 12 |
| `web_scroll` | 5 | 7 | 9 |
| `compare` | 6 | 7 | 8 |
| `stat` | 4 | 5 | 6 |
| `quote` | 5 | 6 | 7 |
| `timeline` | 8 | 10 | 12 |
| `outro` | 2 | 3 | 4 |

## Pacing rules of thumb

### 1. The 3-second rule

In reactive mode, **no scene should exceed 5 seconds without something visually changing**. If your `body` scene is 5 sec, make sure it has an `image` (Ken Burns adds visual motion). If it's text-only, drop to ≤3.5 sec.

### 2. The fast-fast-slow rule

Stack 2–3 fast scenes (≤3 sec each) before any slower beat. Example reactive sequence:

```
hook (4s) → kinetic_type (2s) → context (5s) → broll_montage (5s)
                  ^^^                              ^^^
              fast burst                      slower payoff
```

This rhythm hooks the viewer, then lets them breathe.

### 3. End faster than you start

Last 30% of the video should pace faster than the first 30%. Example educational arc:

```
[hook 5s] [context 6s] [body 8s] [body 7s] [stat 5s] [compare 6s] [body 5s] [outro 3s]
                       ↑ slow, deep                  ↑ accelerating          ↑ snap end
```

### 4. Voiceover sync (when word_timestamps present)

If `word_timestamps` is present on the script, the script_agent's `fix_scene_timing` already aligns `duration_sec` to spoken-word boundaries — trust that output. **Never** manually shorten a scene below its voiceover length, or words will get clipped.

### 5. Silent (no voiceover) videos

When `audio_file` is null and `word_timestamps` is empty, you have full directorial control. Default to slightly faster pacing — silent videos lose attention quicker without audio anchoring.

## Anti-patterns

- ❌ All scenes at the same duration (3, 3, 3, 3, 3) → feels mechanical
- ❌ Two `body` scenes at 8s+ back to back → kills momentum
- ❌ Hook longer than 6 sec → audience already left
- ❌ Total video <12 sec → algorithms underdeliver short content
- ❌ Total reactive video >30 sec → you've turned it into a deep-dive

## Total length formula

A quick check: `sum(scene.duration_sec)` should land in the bands above. If the sum is too long, the easiest cuts are: shorten `body` scenes, drop one `body`, or cut the `compare` scene. If too short, add a `body` or extend the `broll_montage`.

## Cross-references

- Per-scene props: `scene-composition.md`
- Big-picture flow: `video-director.md`
