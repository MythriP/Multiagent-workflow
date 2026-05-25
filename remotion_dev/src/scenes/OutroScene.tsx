// OutroScene — closing card with a ScaleIn handle and animated CTA text.
// A GlowUnderline draws under the handle for a polished finish.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { ScaleIn } from "../animations/ScaleIn";
import { GlowUnderline } from "../animations/GlowUnderline";
import { WordReveal } from "../animations/WordReveal";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { OutroScene as OutroSceneProps, SceneComponentProps } from "../video-types";

type Props = OutroSceneProps & SceneComponentProps;

const HANDLE_FONT_SIZE = 72;
// Rough: 72px * 0.55 ≈ 40px per char
const CHARS_PX = 40;

export const OutroScene: React.FC<Props> = ({
  cta,
  handle,
  accentColor,
  durationFrames,
}) => {
  const displayHandle = handle ?? BRAND.accountHandle;
  const handleWidth = displayHandle.length * CHARS_PX;

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} particleCount={40} maxOpacity={0.28} />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: BRAND.padding.section,
          padding: BRAND.padding.slide,
        }}
      >
        {/* Handle with glow underline */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
          <ScaleIn overshoot>
            <span
              style={{
                fontFamily: BRAND.fontSans,
                fontSize: HANDLE_FONT_SIZE,
                fontWeight: 900,
                color: accentColor,
                letterSpacing: "-0.02em",
              }}
            >
              {displayHandle}
            </span>
          </ScaleIn>

          <Sequence from={18} layout="none">
            <GlowUnderline
              maxWidth={handleWidth}
              color={accentColor}
              thickness={6}
            />
          </Sequence>
        </div>

        {/* CTA text */}
        <Sequence from={12} layout="none">
          <FadeSlide direction="up" durationFrames={20}>
            <WordReveal
              text={cta}
              fontSize={42}
              fontWeight={500}
              color={BRAND.textMuted}
              staggerFrames={5}
              textAlign="center"
            />
          </FadeSlide>
        </Sequence>
      </AbsoluteFill>

      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
