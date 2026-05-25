// Spring-animated number counter. Counts from 0 up to `target` using a
// spring curve for a natural acceleration/deceleration feel.

import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { BRAND } from "../brand";

interface CountUpProps {
  target: number;
  prefix?: string;
  suffix?: string;
  fontSize?: number;
  color?: string;
  delay?: number;
  style?: React.CSSProperties;
}

export const CountUp: React.FC<CountUpProps> = ({
  target,
  prefix = "",
  suffix = "",
  fontSize = 180,
  color = BRAND.accent,
  delay = 0,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - delay,
    fps,
    config: { mass: 1, stiffness: 80, damping: 22 },
  });

  const current = Math.round(Math.min(1, progress) * target);

  return (
    <span
      style={{
        fontFamily: BRAND.fontSans,
        fontSize,
        fontWeight: 900,
        color,
        lineHeight: 1,
        letterSpacing: "-0.04em",
        ...style,
      }}
    >
      {prefix}
      {current.toLocaleString()}
      {suffix}
    </span>
  );
};
