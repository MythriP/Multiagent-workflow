import React from "react";
import { BRAND } from "../brand";

interface AccentTextProps {
  text: string;
  accentWords: string[];
  fontSize: number;
  color?: string;
  accentColor?: string;
  fontWeight?: number | string;
  lineHeight?: number;
  style?: React.CSSProperties;
}

// Renders text with specific words highlighted in the accent color.
// accentWords is a list of words/phrases to colorize.
export const AccentText: React.FC<AccentTextProps> = ({
  text,
  accentWords,
  fontSize,
  color = BRAND.textPrimary,
  accentColor = BRAND.accent,
  fontWeight = 700,
  lineHeight = 1.15,
  style,
}) => {
  if (accentWords.length === 0) {
    return (
      <span
        style={{
          fontFamily: BRAND.fontSans,
          fontSize,
          fontWeight,
          color,
          lineHeight,
          ...style,
        }}
      >
        {text}
      </span>
    );
  }

  // Build a regex that matches any of the accent words (case-insensitive)
  const pattern = accentWords
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const regex = new RegExp(`(${pattern})`, "gi");
  const parts = text.split(regex);

  return (
    <span
      style={{
        fontFamily: BRAND.fontSans,
        fontSize,
        fontWeight,
        color,
        lineHeight,
        ...style,
      }}
    >
      {parts.map((part, i) => {
        const isAccent = accentWords.some(
          (w) => w.toLowerCase() === part.toLowerCase()
        );
        return isAccent ? (
          <span key={i} style={{ color: accentColor }}>
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </span>
  );
};
