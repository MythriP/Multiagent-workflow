// StatScene — showcases a single big metric. The number counts up with a
// spring, then a glow underline draws under the label, followed by an
// optional context line fading in below.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { CountUp } from "../animations/CountUp";
import { GlowUnderline } from "../animations/GlowUnderline";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { StatScene as StatSceneProps, SceneComponentProps } from "../video-types";

type Props = StatSceneProps & SceneComponentProps;

const LABEL_FONT_SIZE = 44;
const LABEL_CHARS_PX = 22; // rough px per char for underline width estimate

export const StatScene: React.FC<Props> = ({
  number,
  label,
  prefix,
  suffix,
  context_line,
  accentColor,
  durationFrames,
}) => {
  // Underline appears roughly when the count finishes (~fps*0.8)
  const underlineStart = 22;
  const contextStart = underlineStart + 28;

  // Approximate label width for underline
  const labelWidth = label.length * LABEL_CHARS_PX;

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 24,
          padding: BRAND.padding.slide,
        }}
      >
        {/* Big number */}
        <CountUp
          target={number}
          prefix={prefix}
          suffix={suffix}
          fontSize={190}
          color={accentColor}
        />

        {/* Label with glow underline */}
        <div style={{ position: "relative", display: "inline-block" }}>
          <FadeSlide direction="up" durationFrames={18}>
            <p
              style={{
                margin: 0,
                fontFamily: BRAND.fontSans,
                fontSize: LABEL_FONT_SIZE,
                fontWeight: 600,
                color: BRAND.textPrimary,
                textAlign: "center",
                letterSpacing: "0.01em",
              }}
            >
              {label}
            </p>
          </FadeSlide>

          <Sequence from={underlineStart} layout="none">
            <GlowUnderline
              maxWidth={labelWidth}
              color={accentColor}
              style={{ position: "relative", marginTop: 4 }}
            />
          </Sequence>
        </div>

        {/* Optional context */}
        {context_line && (
          <Sequence from={contextStart} layout="none">
            <FadeSlide direction="up" durationFrames={18}>
              <p
                style={{
                  margin: 0,
                  fontFamily: BRAND.fontSans,
                  fontSize: BRAND.fontSize.coverTagline,
                  color: BRAND.textMuted,
                  textAlign: "center",
                }}
              >
                {context_line}
              </p>
            </FadeSlide>
          </Sequence>
        )}
      </AbsoluteFill>

      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
