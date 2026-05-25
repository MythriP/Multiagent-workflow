// Fade + slide from a direction. Wrap any element; it animates from
// hidden/offset to fully visible/on-position over `durationFrames`.

import React from "react";
import { interpolate, useCurrentFrame, Easing } from "remotion";

interface FadeSlideProps {
  direction?: "up" | "down" | "left" | "right";
  durationFrames?: number;
  distance?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const FadeSlide: React.FC<FadeSlideProps> = ({
  direction = "up",
  durationFrames = 18,
  distance = 48,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const ease = Easing.out(Easing.cubic);

  const opacity = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: ease,
  });

  const offset = interpolate(frame, [0, durationFrames], [distance, 0], {
    extrapolateRight: "clamp",
    easing: ease,
  });

  const tx = direction === "left" ? -offset : direction === "right" ? offset : 0;
  const ty = direction === "up" ? offset : direction === "down" ? -offset : 0;

  return (
    <div
      style={{
        opacity,
        transform: `translate(${tx}px, ${ty}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
