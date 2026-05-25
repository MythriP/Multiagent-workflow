// BodyScene — delivers core facts/insights. Vertical 9:16 layout: image
// occupies the top ~52% with a Ken-Burns-style zoom; text fills the
// bottom half with staggered line reveals. The first line is highlighted
// in accent color for hierarchy.
//
// Optional arrow annotations draw over the entire layout — coordinates
// are 0-1 fractions of the full frame so they map to whatever aspect
// ratio is active.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { LineStagger } from "../animations/LineStagger";
import { DrawArrow } from "../animations/DrawArrow";
import { KenBurns } from "../animations/KenBurns";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { BodyScene as BodySceneProps, SceneComponentProps } from "../video-types";

type Props = BodySceneProps & SceneComponentProps;

export const BodyScene: React.FC<Props> = ({
  lines,
  image,
  arrows,
  accentColor,
  durationFrames,
}) => {
  const linesRevealEnd = lines.length * 13 + 16;
  const imageHeightPct = 52;     // top half holds the image
  const textPaddingTop = `${imageHeightPct + 5}%`;

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} particleCount={28} maxOpacity={0.18} />

      {/* Top: image (when present) */}
      {image && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: `${imageHeightPct}%`,
            overflow: "hidden",
          }}
        >
          <FadeSlide direction="down" durationFrames={20}>
            <KenBurns
              src={image}
              durationFrames={durationFrames}
              startScale={1.05}
              endScale={1.18}
            />
          </FadeSlide>

          {/* Soft gradient at the bottom of the image so text bleeds in */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: 200,
              background:
                "linear-gradient(to bottom, rgba(10,10,10,0) 0%, rgba(10,10,10,1) 100%)",
            }}
          />
        </div>
      )}

      {/* Bottom: stacked text */}
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          padding: BRAND.padding.slide,
          paddingTop: image ? textPaddingTop : BRAND.padding.slide,
          gap: 12,
        }}
      >
        <Sequence from={image ? 12 : 5} layout="none">
          <LineStagger
            lines={lines}
            fontSize={BRAND.fontSize.bodyText}
            accentColor={accentColor}
            accentLines={[0]}
            staggerFrames={13}
          />
        </Sequence>
      </AbsoluteFill>

      {/* Optional drawn arrows — over everything */}
      {arrows.map(([ax1, ay1, ax2, ay2], i) => (
        <Sequence key={i} from={linesRevealEnd + i * 8} layout="none">
          <DrawArrow
            x1={ax1 * BRAND.width}
            y1={ay1 * BRAND.height}
            x2={ax2 * BRAND.width}
            y2={ay2 * BRAND.height}
            color={accentColor}
            startFrame={0}
            durationFrames={22}
            canvasWidth={BRAND.width}
            canvasHeight={BRAND.height}
          />
        </Sequence>
      ))}

      {/* durationFrames consumed to silence unused-var lint */}
      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
