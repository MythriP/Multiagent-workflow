---
description: Re-render a Remotion video from an existing video_script.json (skips narrative/voiceover).
argument-hint: <video_script.json path>
---

Re-render an existing video script without re-running narrative or voiceover.

1. Validate the path points to a `video_script.json`.
2. Locate the matching `voiceover.mp3` + `word_timestamps.json` in the same folder.
3. Run `cd remotion_dev && npx ts-node scripts/render-video.ts $ARGUMENTS`.
4. Report the output `final.mp4` path under `remotion_dev/outputs/videos/`.
