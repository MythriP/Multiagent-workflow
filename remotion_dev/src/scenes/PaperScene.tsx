// PaperScene — scrolls through a research paper screenshot, drawing circles
// around key highlights at configurable positions. The title fades in at the
// top before scrolling begins.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { DocumentScroll } from "../animations/DocumentScroll";
import { DrawCircle } from "../animations/DrawCircle";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { PaperScene as PaperSceneProps, SceneComponentProps } from "../video-types";

type Props = PaperSceneProps & SceneComponentProps;

export const PaperScene: React.FC<Props> = ({
  paper_image,
  title,
  highlights,
  accentColor,
  durationFrames,
}) => {
  // Distribute circle annotations evenly through the scene
  const circleSpacing = highlights.length
    ? Math.floor((durationFrames * 0.5) / highlights.length)
    : 0;

  return (
    <AbsoluteFill>
      {/* Scrolling document */}
      <DocumentScroll
        src={paper_image}
        durationFrames={durationFrames}
        startY={0}
        endY={-800}
        pauseAt={highlights.length ? 0.45 : undefined}
        pauseFrames={30}
      />

      {/* Title overlay at top */}
      {title && (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "center",
            padding: `${BRAND.padding.slide}px ${BRAND.padding.slide}px 0`,
          }}
        >
          <Sequence layout="none">
            <FadeSlide direction="down" durationFrames={20}>
              <div
                style={{
                  backgroundColor: accentColor,
                  color: "#000",
                  fontFamily: BRAND.fontMono,
                  fontSize: BRAND.fontSize.label,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  padding: "6px 18px",
                  borderRadius: 6,
                }}
              >
                {title}
              </div>
            </FadeSlide>
          </Sequence>
        </AbsoluteFill>
      )}

      {/* Highlight circles */}
      {highlights.map((h, i) => (
        <Sequence
          key={i}
          from={Math.floor(durationFrames * 0.3) + i * circleSpacing}
          layout="none"
        >
          <DrawCircle
            cx={h.cx}
            cy={h.cy}
            radius={h.radius}
            color={accentColor}
            strokeWidth={8}
            durationFrames={22}
            canvasWidth={BRAND.width}
            canvasHeight={BRAND.height}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
