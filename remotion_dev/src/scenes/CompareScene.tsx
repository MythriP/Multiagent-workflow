// CompareScene — split-screen A vs B comparison. The dividing line draws
// downward first, then the two panels MaskReveal from their respective sides.

import React from "react";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from "remotion";
import { MaskReveal } from "../animations/MaskReveal";
import { FadeSlide } from "../animations/FadeSlide";
import { NoiseBackground } from "../animations/NoiseBackground";
import { BRAND } from "../brand";
import type { CompareScene as CompareSceneProps, SceneComponentProps } from "../video-types";

type Props = CompareSceneProps & SceneComponentProps;

export const CompareScene: React.FC<Props> = ({
  left_label,
  left_points,
  right_label,
  right_points,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();

  // Divider line grows from top to bottom over 22 frames
  const dividerProgress = interpolate(frame, [0, 22], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} particleCount={30} maxOpacity={0.18} />

      {/* Divider line */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: BRAND.padding.slide,
          width: 2,
          height: `${dividerProgress * (BRAND.height - BRAND.padding.slide * 2)}px`,
          backgroundColor: accentColor,
          opacity: 0.5,
          transform: "translateX(-50%)",
        }}
      />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "row",
          gap: 0,
        }}
      >
        {/* Left column */}
        <Sequence from={20} layout="none">
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              padding: BRAND.padding.slide,
              paddingRight: BRAND.padding.slide / 2 + 8,
              gap: BRAND.padding.section * 0.6,
            }}
          >
            {/* Left label */}
            <MaskReveal direction="left">
              <div
                style={{
                  fontFamily: BRAND.fontSans,
                  fontSize: 36,
                  fontWeight: 800,
                  color: BRAND.textPrimary,
                  paddingBottom: 8,
                  borderBottom: `3px solid ${accentColor}`,
                  display: "inline-block",
                }}
              >
                {left_label}
              </div>
            </MaskReveal>

            {/* Left points */}
            {left_points.map((pt, i) => (
              <Sequence key={i} from={i * 12 + 10} layout="none">
                <FadeSlide direction="left" durationFrames={16}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 10,
                    }}
                  >
                    <span
                      style={{
                        color: accentColor,
                        fontWeight: 700,
                        fontSize: BRAND.fontSize.bodyText * 0.88,
                        marginTop: 2,
                        flexShrink: 0,
                      }}
                    >
                      ✦
                    </span>
                    <p
                      style={{
                        margin: 0,
                        fontFamily: BRAND.fontSans,
                        fontSize: BRAND.fontSize.bodyText * 0.88,
                        color: BRAND.textPrimary,
                        lineHeight: 1.35,
                        fontWeight: 400,
                      }}
                    >
                      {pt}
                    </p>
                  </div>
                </FadeSlide>
              </Sequence>
            ))}
          </div>
        </Sequence>

        {/* Right column */}
        <Sequence from={26} layout="none">
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              padding: BRAND.padding.slide,
              paddingLeft: BRAND.padding.slide / 2 + 8,
              gap: BRAND.padding.section * 0.6,
            }}
          >
            {/* Right label */}
            <MaskReveal direction="right">
              <div
                style={{
                  fontFamily: BRAND.fontSans,
                  fontSize: 36,
                  fontWeight: 800,
                  color: BRAND.textMuted,
                  paddingBottom: 8,
                  borderBottom: `3px solid rgba(255,255,255,0.2)`,
                  display: "inline-block",
                }}
              >
                {right_label}
              </div>
            </MaskReveal>

            {/* Right points */}
            {right_points.map((pt, i) => (
              <Sequence key={i} from={i * 12 + 10} layout="none">
                <FadeSlide direction="right" durationFrames={16}>
                  <div
                    style={{ display: "flex", alignItems: "flex-start", gap: 10 }}
                  >
                    <span
                      style={{
                        color: BRAND.textDim,
                        fontWeight: 700,
                        fontSize: BRAND.fontSize.bodyText * 0.88,
                        marginTop: 2,
                        flexShrink: 0,
                      }}
                    >
                      ✦
                    </span>
                    <p
                      style={{
                        margin: 0,
                        fontFamily: BRAND.fontSans,
                        fontSize: BRAND.fontSize.bodyText * 0.88,
                        color: BRAND.textMuted,
                        lineHeight: 1.35,
                        fontWeight: 400,
                      }}
                    >
                      {pt}
                    </p>
                  </div>
                </FadeSlide>
              </Sequence>
            ))}
          </div>
        </Sequence>
      </AbsoluteFill>

      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
