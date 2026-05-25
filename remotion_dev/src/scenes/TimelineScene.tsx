// TimelineScene — vertical timeline with events that MaskReveal in sequence.
// The connector line draws downward as new events appear, creating a
// satisfying "story unfolds" feel.

import React from "react";
import { AbsoluteFill, interpolate, Sequence, useCurrentFrame } from "remotion";
import { MaskReveal } from "../animations/MaskReveal";
import { NoiseBackground } from "../animations/NoiseBackground";
import { FadeSlide } from "../animations/FadeSlide";
import { BRAND } from "../brand";
import type { TimelineScene as TimelineSceneProps, SceneComponentProps } from "../video-types";

type Props = TimelineSceneProps & SceneComponentProps;

const EVENT_STAGGER = 20; // frames between each event
const CONNECTOR_DURATION = EVENT_STAGGER - 4;

export const TimelineScene: React.FC<Props> = ({
  title,
  events,
  accentColor,
  durationFrames,
}) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <NoiseBackground accentColor={accentColor} particleCount={30} maxOpacity={0.2} />

      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          padding: BRAND.padding.slide,
          paddingTop: BRAND.padding.slide,
          gap: 0,
        }}
      >
        {/* Optional title */}
        {title && (
          <FadeSlide direction="down" durationFrames={18}>
            <p
              style={{
                margin: "0 0 36px",
                fontFamily: BRAND.fontMono,
                fontSize: BRAND.fontSize.label,
                color: accentColor,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                fontWeight: 700,
              }}
            >
              {title}
            </p>
          </FadeSlide>
        )}

        {/* Events */}
        <div style={{ position: "relative", paddingLeft: 52 }}>
          {/* Vertical line — grows downward */}
          {events.map((_, i) => {
            if (i === 0) return null;
            const lineStart = (i - 1) * EVENT_STAGGER + 8;
            const lineProgress = interpolate(
              frame,
              [lineStart, lineStart + CONNECTOR_DURATION],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return (
              <div
                key={`line-${i}`}
                style={{
                  position: "absolute",
                  left: 15,
                  top: 24 + (i - 1) * 110,
                  width: 3,
                  height: `${lineProgress * 110}px`,
                  backgroundColor: accentColor,
                  borderRadius: 2,
                  opacity: 0.6,
                }}
              />
            );
          })}

          {/* Event rows */}
          {events.map((event, i) => (
            <Sequence key={i} from={i * EVENT_STAGGER} layout="none">
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  marginBottom: 30,
                  gap: 0,
                  position: "relative",
                }}
              >
                {/* Dot */}
                <div
                  style={{
                    position: "absolute",
                    left: -38,
                    top: 6,
                    width: 14,
                    height: 14,
                    borderRadius: "50%",
                    backgroundColor: accentColor,
                    boxShadow: `0 0 10px ${accentColor}`,
                  }}
                />

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <MaskReveal direction="left">
                    <span
                      style={{
                        fontFamily: BRAND.fontMono,
                        fontSize: BRAND.fontSize.label,
                        color: accentColor,
                        fontWeight: 700,
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                      }}
                    >
                      {event.date}
                    </span>
                  </MaskReveal>

                  <Sequence from={6} layout="none">
                    <FadeSlide direction="up" durationFrames={14}>
                      <p
                        style={{
                          margin: 0,
                          fontFamily: BRAND.fontSans,
                          fontSize: BRAND.fontSize.bodyText * 0.88,
                          color: BRAND.textPrimary,
                          fontWeight: 500,
                          lineHeight: 1.35,
                        }}
                      >
                        {event.label}
                      </p>
                    </FadeSlide>
                  </Sequence>
                </div>
              </div>
            </Sequence>
          ))}
        </div>
      </AbsoluteFill>

      {durationFrames > 0 && null}
    </AbsoluteFill>
  );
};
