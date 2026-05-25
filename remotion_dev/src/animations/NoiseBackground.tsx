// Animated dark background with Perlin-noise-driven floating particles.
// Uses @remotion/noise for smooth, non-random movement that looks great
// on video renders (no jitter). Renders as AbsoluteFill.

import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { noise2D } from "@remotion/noise";
import { BRAND } from "../brand";

interface NoiseBackgroundProps {
  accentColor?: string;
  backgroundColor?: string;
  particleCount?: number;
  speed?: number;
  /** Max particle opacity (0–1) */
  maxOpacity?: number;
}

export const NoiseBackground: React.FC<NoiseBackgroundProps> = ({
  accentColor = BRAND.accent,
  backgroundColor = BRAND.background,
  particleCount = 55,
  speed = 0.004,
  maxOpacity = 0.35,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const W = width || BRAND.width;
  const H = height || BRAND.height;
  const t = frame * speed;

  const particles = Array.from({ length: particleCount }, (_, i) => {
    const x = ((noise2D(`px${i}`, t, i * 0.1) + 1) / 2) * W;
    const y = ((noise2D(`py${i}`, t, i * 0.1) + 1) / 2) * H;
    const opacity = ((noise2D(`op${i}`, t, i * 0.1) + 1) / 2) * maxOpacity;
    const r = ((noise2D(`sz${i}`, t, i * 0.1) + 1) / 2) * 3.5 + 0.8;
    return { x, y, opacity, r };
  });

  return (
    <AbsoluteFill style={{ backgroundColor }}>
      <svg
        width={W}
        height={H}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        {particles.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={p.r}
            fill={accentColor}
            opacity={p.opacity}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};
