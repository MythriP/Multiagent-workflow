// Characters scramble randomly then lock into their final values from left to
// right — like a loading decode effect. Great for headlines.

import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { BRAND } from "../brand";

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%&";

interface TextScrambleProps {
  text: string;
  fontSize?: number;
  fontWeight?: number | string;
  color?: string;
  accentColor?: string;
  durationFrames?: number;
  style?: React.CSSProperties;
}

export const TextScramble: React.FC<TextScrambleProps> = ({
  text,
  fontSize = BRAND.fontSize.coverHeadline,
  fontWeight = 900,
  color = BRAND.textPrimary,
  accentColor = BRAND.accent,
  durationFrames = 50,
  style,
}) => {
  const frame = useCurrentFrame();

  const globalProgress = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  const displayed = text.split("").map((char, i) => {
    if (char === " ") return " ";

    const charFraction = i / text.length;
    const charProgress = interpolate(
      globalProgress,
      [charFraction, Math.min(1, charFraction + 1 / text.length + 0.05)],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    if (charProgress >= 1) return char;

    // deterministic scramble — same frame → same chars (no re-render flicker)
    const idx = (frame * 7 + i * 13 + 3) % CHARS.length;
    return CHARS[idx];
  });

  // Characters that have locked in render in accentColor briefly, then white
  const chars = text.split("").map((char, i) => {
    if (char === " ") return { ch: " ", locked: true };
    const charFraction = i / text.length;
    const locked =
      interpolate(globalProgress, [charFraction, charFraction + 0.02], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }) >= 1;
    return { ch: displayed[i], locked };
  });

  return (
    <span
      style={{
        fontFamily: BRAND.fontSans,
        fontSize,
        fontWeight,
        letterSpacing: "-0.02em",
        ...style,
      }}
    >
      {chars.map(({ ch, locked }, i) => (
        <span key={i} style={{ color: locked ? color : accentColor }}>
          {ch}
        </span>
      ))}
    </span>
  );
};
