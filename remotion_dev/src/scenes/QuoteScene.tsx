// QuoteScene — a pull quote that typewriter-reveals, then the speaker name
// slides in from the right. A large decorative quotation mark adds visual depth.

import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { TypeWriter } from "../animations/TypeWriter";
import { FadeSlide } from "../animations/FadeSlide";
import { NoiseBackground } from "../animations/NoiseBackground";
import { Sequence } from "remotion";
import { BRAND } from "../brand";
import type { QuoteScene as QuoteSceneProps, SceneComponentProps } from "../video-types";

type Props = QuoteSceneProps & SceneComponentProps;

export const QuoteScene: React.FC<Props> = ({
  text,
  speaker,
  role,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();

  // Quote mark fades in slowly
  const quoteMark = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Speaker attribution appears after quote finishes typing
  const charsPerFrame = 0.6;
  const speakerStart = Math.ceil(text.length / charsPerFrame) + 10;

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} particleCount={30} maxOpacity={0.18} />

      {/* Decorative " */}
      <div
        style={{
          position: "absolute",
          top: BRAND.padding.slide - 20,
          left: BRAND.padding.slide - 10,
          fontFamily: BRAND.fontSans,
          fontSize: 240,
          fontWeight: 900,
          color: accentColor,
          opacity: quoteMark * 0.12,
          lineHeight: 1,
          userSelect: "none",
        }}
      >
        &ldquo;
      </div>

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: BRAND.padding.slide,
          paddingTop: BRAND.padding.slide + 40,
          gap: BRAND.padding.section,
        }}
      >
        {/* Quote body */}
        <TypeWriter
          text={`"${text}"`}
          fontSize={BRAND.fontSize.bodyTextLarge}
          color={BRAND.textPrimary}
          charsPerFrame={charsPerFrame}
          showCursor={false}
          style={{
            fontStyle: "italic",
            lineHeight: 1.4,
            fontWeight: 500,
          }}
        />

        {/* Speaker */}
        {speaker && (
          <Sequence from={speakerStart} layout="none">
            <FadeSlide direction="right" durationFrames={20}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  borderLeft: `4px solid ${accentColor}`,
                  paddingLeft: 20,
                  gap: 4,
                }}
              >
                <span
                  style={{
                    fontFamily: BRAND.fontSans,
                    fontSize: 32,
                    fontWeight: 700,
                    color: accentColor,
                  }}
                >
                  — {speaker}
                </span>
                {role && (
                  <span
                    style={{
                      fontFamily: BRAND.fontMono,
                      fontSize: BRAND.fontSize.label,
                      color: BRAND.textMuted,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    {role}
                  </span>
                )}
              </div>
            </FadeSlide>
          </Sequence>
        )}
      </AbsoluteFill>

      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
