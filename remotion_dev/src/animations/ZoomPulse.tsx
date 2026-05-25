// Zoom in to a peak scale then spring back to 1. Use to draw attention to a
// word or element at a specific moment in the timeline.

import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig, Easing } from "remotion";

interface ZoomPulseProps {
  peakFrame?: number;    // frame at which scale is maximum
  peakScale?: number;    // maximum scale
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const ZoomPulse: React.FC<ZoomPulseProps> = ({
  peakFrame = 12,
  peakScale = 1.45,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let scale: number;
  if (frame <= peakFrame) {
    scale = interpolate(frame, [0, peakFrame], [1, peakScale], {
      easing: Easing.out(Easing.cubic),
      extrapolateRight: "clamp",
    });
  } else {
    scale =
      peakScale -
      (peakScale - 1) *
        spring({
          frame: frame - peakFrame,
          fps,
          config: { mass: 0.6, stiffness: 200, damping: 14 },
        });
  }

  return (
    <div
      style={{
        display: "inline-block",
        transform: `scale(${Math.max(0, scale)})`,
        transformOrigin: "center center",
        ...style,
      }}
    >
      {children}
    </div>
  );
};
