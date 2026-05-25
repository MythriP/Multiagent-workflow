// KineticTypeScene — punchy word-by-word kinetic typography on a clean
// background. Designed for "money lines" of voiceover where the words
// themselves should carry visual energy. Each word lands with a spring
// scale, slight rotation, and accent words pop in the brand color.
//
// Use this for hot-take statements, opinion lines, or punchline moments.

import React from "react";
import {
  AbsoluteFill,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { KenBurns } from "../animations/KenBurns";
import { NoiseBackground } from "../animations/NoiseBackground";
import { BRAND } from "../brand";
import type {
  KineticTypeScene as KineticTypeProps,
  SceneComponentProps,
} from "../video-types";

type Props = KineticTypeProps & SceneComponentProps;

export const KineticTypeScene: React.FC<Props> = ({
  text,
  accent_words,
  words_per_burst,
  bg_image,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const allWords = text.split(/\s+/).filter(Boolean);
  const accentSet = new Set(accent_words.map((w) => w.toLowerCase()));

  // Group words into bursts (e.g. words_per_burst=2 → ["Hot take", "Models", "are sentient"])
  const bursts: string[][] = [];
  for (let i = 0; i < allWords.length; i += words_per_burst) {
    bursts.push(allWords.slice(i, i + words_per_burst));
  }

  // Available frames per burst — leave 8 frames at end for hold
  const holdFrames = Math.min(20, Math.floor(durationFrames * 0.15));
  const burstFrames = Math.max(
    8,
    Math.floor((durationFrames - holdFrames) / Math.max(1, bursts.length))
  );

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background }}>
      {bg_image ? (
        <>
          <KenBurns src={bg_image} durationFrames={durationFrames} endScale={1.1} />
          <AbsoluteFill style={{ backgroundColor: "rgba(0,0,0,0.72)" }} />
        </>
      ) : (
        <NoiseBackground accentColor={accentColor} particleCount={42} maxOpacity={0.22} />
      )}

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: BRAND.padding.slide,
          gap: 28,
        }}
      >
        {bursts.map((burst, bi) => {
          const burstStart = bi * burstFrames;
          const burstEnd = burstStart + burstFrames;
          // After this burst's "in" window (~12 frames), it remains visible until
          // the next burst arrives — but for a kinetic feel, we collapse old
          // bursts down with a quick scale shrink + opacity drop.
          const isCurrent = frame >= burstStart && frame < burstEnd;
          const isPast = frame >= burstEnd;

          // "In" spring for the active burst
          const burstSpring = spring({
            frame: frame - burstStart,
            fps,
            config: { mass: 0.4, stiffness: 320, damping: 14 },
          });
          const inScale = burstSpring;

          // "Out" interpolation for past bursts: fade & shrink slightly
          const outProgress = isPast
            ? interpolate(frame, [burstEnd, burstEnd + 8], [0, 1], {
                extrapolateRight: "clamp",
              })
            : 0;
          const outOpacity = 1 - outProgress * 0.7;
          const outScale = 1 - outProgress * 0.06;

          const scale = isCurrent ? inScale : outScale;
          const opacity = isCurrent
            ? interpolate(frame, [burstStart, burstStart + 6], [0, 1], {
                extrapolateRight: "clamp",
              })
            : isPast
              ? outOpacity
              : 0;

          return (
            <div
              key={bi}
              style={{
                display: "flex",
                flexWrap: "wrap",
                justifyContent: "center",
                gap: "0.3em",
                opacity,
                transform: `scale(${Math.max(0, scale)})`,
                transformOrigin: "center",
              }}
            >
              {burst.map((word, wi) => {
                const bare = word.toLowerCase().replace(/[^a-z0-9]/g, "");
                const isAccent = accentSet.has(bare);
                return (
                  <span
                    key={wi}
                    style={{
                      fontFamily: BRAND.fontSans,
                      fontSize: BRAND.fontSize.bodyTextLarge,
                      fontWeight: 900,
                      letterSpacing: "-0.02em",
                      color: isAccent ? accentColor : BRAND.textPrimary,
                      textShadow: isAccent ? `0 0 30px ${accentColor}88` : "none",
                      lineHeight: 1.05,
                    }}
                  >
                    {word}
                  </span>
                );
              })}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
