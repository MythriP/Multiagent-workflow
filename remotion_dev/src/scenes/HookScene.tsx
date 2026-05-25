// HookScene — opening card. Big kinetic headline (WordReveal) over either a
// Ken-Burns photo or an animated noise background. Accent words render in the
// brand accent color. An optional tagline fades in after the headline resolves.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { WordReveal } from "../animations/WordReveal";
import { KenBurns } from "../animations/KenBurns";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { HookScene as HookSceneProps, SceneComponentProps } from "../video-types";

type Props = HookSceneProps & SceneComponentProps;

export const HookScene: React.FC<Props> = ({
  headline,
  accent_words,
  bg_image,
  tagline,
  accentColor,
  durationFrames,
}) => {
  const wordCount = headline.split(" ").length;
  const headlineRevealDone = wordCount * 7 + 8; // approximate frame all words land

  return (
    <AbsoluteFill>
      {/* Background layer */}
      {bg_image ? (
        <KenBurns
          src={bg_image}
          durationFrames={durationFrames}
          startScale={1.0}
          endScale={1.12}
        />
      ) : (
        <NoiseBackground accentColor={accentColor} />
      )}

      {/* Darkening overlay when a photo is used */}
      {bg_image && (
        <AbsoluteFill
          style={{ backgroundColor: "rgba(0,0,0,0.58)" }}
        />
      )}

      {/* Headline */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: BRAND.padding.slide,
          gap: BRAND.padding.section,
        }}
      >
        <WordReveal
          text={headline}
          accentWords={accent_words}
          accentColor={accentColor}
          fontSize={BRAND.fontSize.coverHeadline}
          staggerFrames={7}
          textAlign="center"
        />

        {tagline && (
          <Sequence from={headlineRevealDone} layout="none">
            <FadeSlide direction="up" durationFrames={18}>
              <p
                style={{
                  margin: 0,
                  fontFamily: BRAND.fontSans,
                  fontSize: BRAND.fontSize.coverTagline,
                  color: BRAND.textMuted,
                  textAlign: "center",
                  fontWeight: 400,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                {tagline}
              </p>
            </FadeSlide>
          </Sequence>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
