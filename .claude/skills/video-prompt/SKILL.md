---
name: video-prompt
description: Engineer cinematic prompts for AI text-to-video and image-to-video models (Veo 3.1 Fast, Kling, Sora). Use whenever the pipeline needs to generate a short clip from a text prompt or a reference image. Returns a single prose prompt the video model will execute well.
---

# Cinematic Video Prompt Engineering

This skill is the source of truth for how the script_agent talks to AI video
models (currently fal.ai Veo 3.1 Fast). Whenever a beat or scene needs a
generated clip, build the prompt with this skill, not from intuition.

## When to use this skill

Use this skill whenever you would otherwise paste a freeform "make a video of
X" sentence into a video generator. That includes:

- A scene_writer beat that calls for AI b-roll (no source media available).
- A "specific named person doing a thing" hero shot (image-to-video using a
  reference photo).
- A diagram or screenshot that should be animated (i2v on the screenshot).
- An ambient backdrop clip used behind text-only scenes.

Do NOT use this skill for:

- Stock-footage queries (those go to Pexels and are different — short, generic).
- Existing media on disk (use the screenshot or video as-is).
- Avatar lipsync (that goes through `lipsync.py`, not video_gen).

## Veo 3.1 Fast capabilities and limits

- Accepts a single reference image (image-to-video). Best for face anchoring.
- Accepts a single text prompt (text-to-video).
- Duration 4 to 8 seconds. Longer requests get clamped.
- Aspect ratios: "9:16" (default for reels), "16:9", "1:1".
- Hallucinates text onscreen if you don't say "no captions". Always include
  the no-text guardrail.
- Hallucinates logos / watermarks. Always include the no-logo guardrail.

## Prompt anatomy (use this every time)

Every prompt is 3 to 4 short sentences in this order:

1. SUBJECT sentence: who or what, doing what, where. Concrete and specific.
2. CINEMATOGRAPHY sentence: lens, lighting, camera move, palette. This is
   where the vibe profile's `video_gen_modifiers` are appended verbatim.
3. (Optional) EXTRA STYLE sentence: scene-specific overrides like
   "no zoom, framing locked".
4. GUARDRAIL sentence (always present): no captions, no watermarks, no logos,
   photorealistic, stable framing, natural motion.

## Examples

### Tier 1 hero shot (image-to-video, named person)

Subject reference image: `media/sam-altman.jpg`
Subject prompt:

> Sam Altman, in a dark blue knit sweater, walks across an empty stage and
> turns toward the audience, hand raised mid-gesture.

Final prompt after composition with vibe modifiers (vibe = AI-safety-tense):

> Sam Altman, in a dark blue knit sweater, walks across an empty stage and
> turns toward the audience, hand raised mid-gesture. Anamorphic 50mm,
> single hard key light from screen left, near-black backdrop, slow dolly-in.
> No on-screen captions. No watermarks. No logos. Photorealistic, stable
> framing, natural motion.

### Tier 2 specific action (text-to-video)

Subject prompt:

> Two researchers stand at a whiteboard covered in handwritten matrices,
> one pointing at a highlighted equation while the other nods.

Final prompt (vibe = science-discovery):

> Two researchers stand at a whiteboard covered in handwritten matrices,
> one pointing at a highlighted equation while the other nods.
> Documentary 35mm, soft north-facing window light, muted warm palette,
> shallow depth of field. No on-screen captions. No watermarks. No logos.
> Photorealistic, stable framing, natural motion.

### Tier 3 ambient b-roll (text-to-video)

Subject prompt:

> Macro shot of cooling fans spinning inside a server rack, blue LEDs
> reflecting on dust particles in the air.

Final prompt (vibe = clean-tech-serious):

> Macro shot of cooling fans spinning inside a server rack, blue LEDs
> reflecting on dust particles in the air. Cinematic 35mm, shallow depth
> of field, single LED key, near-black background. No on-screen captions.
> No watermarks. No logos. Photorealistic, stable framing, natural motion.

## What to avoid

- Vague subjects: "AI doing things" is unusable. Pick a concrete scene.
- Long comma soups: "cinematic, beautiful, 4k, masterpiece, ultra-realistic"
  is noise. Use lens + lighting + palette instead.
- Onscreen text requests: Veo will paint distorted gibberish. Add captions
  in Remotion later.
- Multiple camera moves in one prompt: "dolly-in then orbit then crash zoom"
  produces a smeared frame. One move per clip.
- Hands holding objects mid-motion: notorious failure mode. Frame the hand
  static, let the rest of the scene move.
- Requesting specific brand names ("a person holding a Pinch device"). Veo
  hallucinates a generic version with corrupted logo. Describe what the
  thing looks like instead.

## Calling the helper from Python

```python
from video_gen import generate_for_beat

mp4_path = generate_for_beat(
    subject_prompt="Two researchers at a whiteboard with handwritten matrices.",
    vibe_modifiers=vibe.video_gen_modifiers,
    duration_sec=6.0,
    aspect_ratio="9:16",
    label="researchers_whiteboard",
    out_dir=out_dir,
    fal_key=FAL_KEY,
)
```

The helper composes the final prompt (subject + vibe + guardrails), checks
the cache, and only hits fal.ai on a miss. Results live under
`<out_dir>/media/genvid_<label>_<hash>.mp4`.

## Reference-image (i2v) tips

- Pass a tight headshot or 3/4 portrait, not a full-body shot. Veo anchors
  the face better when the face is large in the reference.
- The subject_prompt should describe what the person DOES, not what they
  LOOK like. Veo already has the face. Don't waste tokens on hair color.
- Backgrounds in the reference image leak into the output. If you don't
  want the kitchen behind the person, use a chromakey-cutout photo.

## Fallback behavior

If `video_gen.generate_video()` returns None, the scene writer should fall
back to:

1. A Pexels stock video on the same theme (`media.fetch_pexels_video()`).
2. A static image with a slow slide-in (no synthetic motion).

Never silently render an empty scene. Every scene must have a visible
backdrop or foreground.