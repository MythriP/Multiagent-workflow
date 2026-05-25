// ContextScene — sets up the "why this matters" moment. Shows a source label
// + optional image/video, then lines stagger in below. Supports video clips
// via <Video> for rich b-roll context.

import React from "react";
import { AbsoluteFill, Sequence, Video } from "remotion";
import { LineStagger } from "../animations/LineStagger";
import { KenBurns } from "../animations/KenBurns";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { MaskReveal } from "../animations/MaskReveal";
import { BRAND } from "../brand";
import type { ContextScene as ContextSceneProps, SceneComponentProps } from "../video-types";

type Props = ContextSceneProps & SceneComponentProps;

export const ContextScene: React.FC<Props> = ({
  lines,
  source_image,
  source_label,
  source_video,
  accentColor,
  durationFrames,
}) => {
  const hasMedia = !!(source_image || source_video);

  return (
    <AbsoluteFill>
      {/* Background */}
      {source_image && !source_video && (
        <KenBurns src={source_image} durationFrames={durationFrames} endScale={1.08} />
      )}
      {source_video && (
        <AbsoluteFill>
          <Video
            src={source_video}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}
      {!hasMedia && <NoiseBackground accentColor={accentColor} />}

      {/* Dark overlay for legibility */}
      {hasMedia && (
        <AbsoluteFill style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.72) 60%, rgba(0,0,0,0.88) 100%)" }} />
      )}

      {/* Content */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          padding: BRAND.padding.slide,
          paddingBottom: BRAND.padding.slide + 20,
          gap: 28,
        }}
      >
        {/* Source chip */}
        {source_label && (
          <Sequence from={5} layout="none">
            <FadeSlide direction="right" durationFrames={16}>
              <MaskReveal direction="left">
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    backgroundColor: accentColor,
                    color: "#000",
                    fontFamily: BRAND.fontMono,
                    fontSize: BRAND.fontSize.label,
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    padding: "6px 16px",
                    borderRadius: 6,
                  }}
                >
                  {source_label}
                </div>
              </MaskReveal>
            </FadeSlide>
          </Sequence>
        )}

        {/* Lines */}
        <Sequence from={source_label ? 14 : 5} layout="none">
          <LineStagger
            lines={lines}
            fontSize={BRAND.fontSize.bodyText}
            accentColor={accentColor}
            staggerFrames={13}
          />
        </Sequence>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
