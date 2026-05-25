// Typewriter effect — characters reveal one by one with a blinking cursor.
// `charsPerFrame` controls speed (0.5 = one char every 2 frames).

import React from "react";
import { useCurrentFrame } from "remotion";
import { BRAND } from "../brand";

interface TypeWriterProps {
  text: string;
  fontSize?: number;
  color?: string;
  charsPerFrame?: number;
  showCursor?: boolean;
  style?: React.CSSProperties;
}

export const TypeWriter: React.FC<TypeWriterProps> = ({
  text,
  fontSize = BRAND.fontSize.bodyText,
  color = BRAND.textPrimary,
  charsPerFrame = 0.6,
  showCursor = true,
  style,
}) => {
  const frame = useCurrentFrame();

  const visible = Math.min(text.length, Math.floor(frame * charsPerFrame));
  // blink every 30 frames, only while still typing
  const cursorOn = showCursor && (visible < text.length || frame % 30 < 18);

  return (
    <span
      style={{
        fontFamily: BRAND.fontMono,
        fontSize,
        color,
        whiteSpace: "pre-wrap",
        ...style,
      }}
    >
      {text.slice(0, visible)}
      {cursorOn && (
        <span style={{ opacity: 0.8, color: BRAND.accent }}>█</span>
      )}
    </span>
  );
};
