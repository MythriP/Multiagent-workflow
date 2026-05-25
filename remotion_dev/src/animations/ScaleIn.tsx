// Scale-in entry. Wraps any element with a spring-driven scale entrance.
// `overshoot: true` (default) gives a satisfying elastic pop.

import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

interface ScaleInProps {
  delay?: number;      // delay in frames before animation starts
  overshoot?: boolean; // elastic overshoot vs smooth ease
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const ScaleIn: React.FC<ScaleInProps> = ({
  delay = 0,
  overshoot = true,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    frame: frame - delay,
    fps,
    config: overshoot
      ? { mass: 0.5, stiffness: 300, damping: 10 }
      : { mass: 1, stiffness: 150, damping: 22 },
  });

  return (
    <div
      style={{
        transform: `scale(${Math.max(0, scale)})`,
        display: "inline-block",
        transformOrigin: "center center",
        ...style,
      }}
    >
      {children}
    </div>
  );
};
