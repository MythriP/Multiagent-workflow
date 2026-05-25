// Slowly scrolls through a tall document/paper screenshot (vertical pan).
// Gradient overlays at top and bottom give a cinematic framed look.
// Pair with DrawCircle to annotate interesting sections.

import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, Easing } from "remotion";

interface DocumentScrollProps {
  src: string;
  /** Total frames for this scroll (pass the scene's durationFrames) */
  durationFrames: number;
  /** Starting translateY in px (0 = top of image visible) */
  startY?: number;
  /** Ending translateY in px (negative = scroll down) */
  endY?: number;
  /** Fraction (0–1) at which to pause scrolling mid-document */
  pauseAt?: number;
  /** Duration of the pause in frames */
  pauseFrames?: number;
}

export const DocumentScroll: React.FC<DocumentScrollProps> = ({
  src,
  durationFrames,
  startY = 0,
  endY = -700,
  pauseAt,
  pauseFrames = 20,
}) => {
  const frame = useCurrentFrame();

  let progress: number;
  if (pauseAt != null) {
    // Before pause
    const prePauseFrames = durationFrames * pauseAt;
    const postStartFrame = prePauseFrames + pauseFrames;
    if (frame < prePauseFrames) {
      progress = interpolate(frame, [0, prePauseFrames], [0, pauseAt], {
        extrapolateRight: "clamp",
        easing: Easing.inOut(Easing.cubic),
      });
    } else if (frame < postStartFrame) {
      progress = pauseAt;
    } else {
      progress = interpolate(
        frame,
        [postStartFrame, durationFrames],
        [pauseAt, 1],
        { extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) }
      );
    }
  } else {
    progress = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.cubic),
    });
  }

  const ty = startY + (endY - startY) * progress;

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#0A0A0A" }}>
      <div
        style={{
          position: "absolute",
          width: "100%",
          transform: `translateY(${ty}px)`,
        }}
      >
        <Img
          src={src}
          style={{ width: "100%", display: "block" }}
        />
      </div>

      {/* Fade-out edge gradients */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 120,
          background: "linear-gradient(to bottom, #0A0A0A 0%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 120,
          background: "linear-gradient(to top, #0A0A0A 0%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
