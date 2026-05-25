// Slow zoom + optional pan on an image. Classic Ken Burns effect for giving
// still photos cinematic life. Renders as an AbsoluteFill background layer.

import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, Easing } from "remotion";

interface KenBurnsProps {
  src: string;
  /** Total frames this effect spans (pass the scene's durationFrames) */
  durationFrames: number;
  startScale?: number;
  endScale?: number;
  /** Pan percentage offset at start (x, y) in % of image size */
  startOffsetX?: number;
  startOffsetY?: number;
  endOffsetX?: number;
  endOffsetY?: number;
}

export const KenBurns: React.FC<KenBurnsProps> = ({
  src,
  durationFrames,
  startScale = 1.0,
  endScale = 1.12,
  startOffsetX = 0,
  startOffsetY = 0,
  endOffsetX = -2,
  endOffsetY = 0,
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });

  const scale = startScale + (endScale - startScale) * progress;
  const ox = startOffsetX + (endOffsetX - startOffsetX) * progress;
  const oy = startOffsetY + (endOffsetY - startOffsetY) * progress;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${ox}%, ${oy}%)`,
          transformOrigin: "center center",
        }}
      />
    </AbsoluteFill>
  );
};
