// Word-by-word reveal with spring scale + opacity. Each word springs in
// with a configurable stagger. Words matching `accentWords` render in
// `accentColor` for kinetic emphasis.

import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { BRAND } from "../brand";

export interface WordRevealProps {
  text: string;
  fontSize?: number;
  fontWeight?: number | string;
  color?: string;
  accentWords?: string[];
  accentColor?: string;
  staggerFrames?: number;
  textAlign?: React.CSSProperties["textAlign"];
  style?: React.CSSProperties;
  wordStyle?: React.CSSProperties;
}

export const WordReveal: React.FC<WordRevealProps> = ({
  text,
  fontSize = BRAND.fontSize.coverHeadline,
  fontWeight = 900,
  color = BRAND.textPrimary,
  accentWords = [],
  accentColor = BRAND.accent,
  staggerFrames = 7,
  textAlign = "center",
  style,
  wordStyle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = text.split(" ");
  const accentSet = new Set(accentWords.map((w) => w.toLowerCase()));

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.28em",
        justifyContent: textAlign === "center" ? "center" : "flex-start",
        ...style,
      }}
    >
      {words.map((word, i) => {
        const startFrame = i * staggerFrames;

        const scale = spring({
          frame: frame - startFrame,
          fps,
          config: { mass: 0.45, stiffness: 380, damping: 12 },
        });

        const opacity = interpolate(
          frame,
          [startFrame, startFrame + 6],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        const bare = word.toLowerCase().replace(/[^a-z]/g, "");
        const isAccent = accentSet.has(bare);

        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              fontFamily: BRAND.fontSans,
              fontSize,
              fontWeight,
              color: isAccent ? accentColor : color,
              transform: `scale(${Math.max(0, scale)})`,
              opacity,
              lineHeight: 1.1,
              ...wordStyle,
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
