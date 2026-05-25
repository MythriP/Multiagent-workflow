// Renders an array of text lines that stagger in one by one via FadeSlide.
// Each line enters from below after the previous one finishes arriving.

import React from "react";
import { Sequence } from "remotion";
import { FadeSlide } from "./FadeSlide";
import { BRAND } from "../brand";

export interface LineStaggerProps {
  lines: string[];
  fontSize?: number;
  color?: string;
  accentColor?: string;
  accentLines?: number[]; // indices of lines to highlight in accentColor
  lineHeight?: number;
  staggerFrames?: number;
  entryDuration?: number;
  style?: React.CSSProperties;
  lineStyle?: React.CSSProperties;
}

export const LineStagger: React.FC<LineStaggerProps> = ({
  lines,
  fontSize = BRAND.fontSize.bodyText,
  color = BRAND.textPrimary,
  accentColor = BRAND.accent,
  accentLines = [],
  lineHeight = 1.35,
  staggerFrames = 14,
  entryDuration = 16,
  style,
  lineStyle,
}) => {
  const accentSet = new Set(accentLines);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: `${fontSize * 0.3}px`, ...style }}>
      {lines.map((line, i) => (
        <Sequence key={i} from={i * staggerFrames} layout="none">
          <FadeSlide direction="up" durationFrames={entryDuration}>
            <p
              style={{
                margin: 0,
                fontFamily: BRAND.fontSans,
                fontSize,
                fontWeight: accentSet.has(i) ? 700 : 400,
                color: accentSet.has(i) ? accentColor : color,
                lineHeight,
                ...lineStyle,
              }}
            >
              {line}
            </p>
          </FadeSlide>
        </Sequence>
      ))}
    </div>
  );
};
