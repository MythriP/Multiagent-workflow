// WebScrollScene — fakes scrolling through a web article screenshot,
// pausing partway down to highlight a key section. Use this for "here's
// the source" moments — citing the original article visually instead of
// just naming it.
//
// Visual: dark frame, the screenshot scrolls down with cinematic gradient
// edges, a source-label chip pinned to the top, and an optional highlight
// circle drawn around the key region at the pause point.

import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { DocumentScroll } from "../animations/DocumentScroll";
import { DrawCircle } from "../animations/DrawCircle";
import { FadeSlide } from "../animations/FadeSlide";
import { MaskReveal } from "../animations/MaskReveal";
import { BRAND } from "../brand";
import type {
  WebScrollScene as WebScrollProps,
  SceneComponentProps,
} from "../video-types";

type Props = WebScrollProps & SceneComponentProps;

export const WebScrollScene: React.FC<Props> = ({
  screenshot,
  source_label,
  highlight_y,
  highlight_label,
  accentColor,
  durationFrames,
}) => {
  const hasHighlight = highlight_y != null;
  const pauseAt = hasHighlight ? 0.5 : undefined;

  // Compute when the circle should appear (right after the scroll pauses)
  const pausePoint = pauseAt != null ? Math.floor(durationFrames * pauseAt) : 0;
  const circleStart = pausePoint + 4;

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background }}>
      <DocumentScroll
        src={screenshot}
        durationFrames={durationFrames}
        startY={0}
        endY={-1100}
        pauseAt={pauseAt}
        pauseFrames={28}
      />

      {/* Source label chip — top */}
      {source_label && (
        <AbsoluteFill
          style={{
            display: "flex",
            justifyContent: "flex-start",
            alignItems: "flex-start",
            padding: BRAND.padding.slide,
          }}
        >
          <Sequence layout="none">
            <FadeSlide direction="down" durationFrames={16}>
              <MaskReveal direction="left">
                <div
                  style={{
                    backgroundColor: accentColor,
                    color: "#000",
                    fontFamily: BRAND.fontMono,
                    fontSize: BRAND.fontSize.label,
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    padding: "8px 18px",
                    borderRadius: 6,
                  }}
                >
                  {source_label}
                </div>
              </MaskReveal>
            </FadeSlide>
          </Sequence>
        </AbsoluteFill>
      )}

      {/* Highlight circle at pause point */}
      {hasHighlight && (
        <Sequence from={circleStart} layout="none">
          <DrawCircle
            cx={BRAND.width / 2}
            cy={highlight_y!}
            radius={140}
            color={accentColor}
            strokeWidth={9}
            durationFrames={24}
            canvasWidth={BRAND.width}
            canvasHeight={BRAND.height}
          />
        </Sequence>
      )}

      {/* Highlight label below circle */}
      {hasHighlight && highlight_label && (
        <Sequence from={circleStart + 14} layout="none">
          <AbsoluteFill
            style={{
              display: "flex",
              justifyContent: "flex-start",
              alignItems: "center",
              flexDirection: "column",
              paddingTop: highlight_y! + 180,
            }}
          >
            <FadeSlide direction="up" durationFrames={16}>
              <div
                style={{
                  backgroundColor: "rgba(0,0,0,0.85)",
                  color: BRAND.textPrimary,
                  fontFamily: BRAND.fontSans,
                  fontSize: 36,
                  fontWeight: 700,
                  padding: "12px 24px",
                  borderRadius: 10,
                  border: `2px solid ${accentColor}`,
                  textAlign: "center",
                  maxWidth: BRAND.width - 200,
                }}
              >
                {highlight_label}
              </div>
            </FadeSlide>
          </AbsoluteFill>
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
