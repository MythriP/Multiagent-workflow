// Horizontal wipe-reveal using CSS clip-path. The content sweeps in from
// one side as if pulled out from behind a curtain.

import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

interface MaskRevealProps {
  direction?: "left" | "right";
  delay?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const MaskReveal: React.FC<MaskRevealProps> = ({
  direction = "left",
  delay = 0,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - delay,
    fps,
    config: { mass: 0.8, stiffness: 120, damping: 20 },
  });

  const hidden = (1 - Math.min(1, progress)) * 100;

  const clipPath =
    direction === "left"
      ? `inset(0 ${hidden}% 0 0)`
      : `inset(0 0 0 ${hidden}%)`;

  return (
    <div style={{ clipPath, ...style }}>
      {children}
    </div>
  );
};
