// Animated underline that draws left-to-right with a soft glow. Typically
// placed as an absolute-positioned sibling under a text element.

import React from "react";
import { interpolate, useCurrentFrame, Easing } from "remotion";
import { BRAND } from "../brand";

interface GlowUnderlineProps {
  maxWidth: number;       // px width at 100% — match the parent text width
  color?: string;
  thickness?: number;
  startFrame?: number;
  durationFrames?: number;
  blur?: number;          // glow blur radius in px
  style?: React.CSSProperties;
}

export const GlowUnderline: React.FC<GlowUnderlineProps> = ({
  maxWidth,
  color = BRAND.accent,
  thickness = 5,
  startFrame = 0,
  durationFrames = 22,
  blur = 10,
  style,
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  const width = progress * maxWidth;

  // Subtle pulsing glow after fully drawn
  const glowPulse =
    progress >= 1
      ? 0.75 + 0.25 * Math.sin((frame - startFrame - durationFrames) * 0.12)
      : progress;

  return (
    <div
      style={{
        height: thickness,
        width,
        borderRadius: thickness,
        backgroundColor: color,
        boxShadow: `0 0 ${blur}px ${blur / 2}px ${color}`,
        opacity: glowPulse,
        ...style,
      }}
    />
  );
};
