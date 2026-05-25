// BRollMontageScene — rapid-fire image cycling. Each image gets a brief
// Ken-Burns-style zoom and crossfades into the next. Designed for
// reactive content where you want visual density: voiceover keeps talking
// while images flip through every 0.6-1.2 sec.
//
// Optional per-image caption chips overlay each image. Optional title chip
// stays pinned at the top throughout the montage.

import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  useCurrentFrame,
  Easing,
} from "remotion";
import { FadeSlide } from "../animations/FadeSlide";
import { MaskReveal } from "../animations/MaskReveal";
import { BRAND } from "../brand";
import type {
  BRollMontageScene as BRollMontageProps,
  SceneComponentProps,
} from "../video-types";

type Props = BRollMontageProps & SceneComponentProps;

interface MontageImageProps {
  src: string;
  caption?: string;
  durationFrames: number;
  accentColor: string;
  index: number;
}

const MontageImage: React.FC<MontageImageProps> = ({
  src,
  caption,
  durationFrames,
  accentColor,
  index,
}) => {
  const frame = useCurrentFrame();

  // Each image has its own micro Ken Burns: alternates zoom-in / zoom-out
  // and slight pan direction so the montage doesn't feel mechanical.
  const zoomIn = index % 2 === 0;
  const startScale = zoomIn ? 1.0 : 1.15;
  const endScale = zoomIn ? 1.15 : 1.0;
  const offsetX = (index % 4) - 1.5; // -1.5 .. 1.5

  const progress = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.quad),
  });

  const scale = startScale + (endScale - startScale) * progress;
  const tx = offsetX * progress;

  // Quick fade in for first ~6 frames, fade out for last ~6
  const fadeIn = interpolate(frame, [0, 5], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(
    frame,
    [Math.max(durationFrames - 5, 0), durationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale}) translate(${tx}%, 0)`,
            transformOrigin: "center center",
          }}
        />
      </AbsoluteFill>

      {/* Subtle dark gradient bottom for caption legibility */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.0) 35%)",
        }}
      />

      {/* Per-image caption chip */}
      {caption && (
        <Sequence from={3} layout="none">
          <AbsoluteFill
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
              alignItems: "center",
              padding: BRAND.padding.slide,
              paddingBottom: BRAND.padding.slide + 80,
            }}
          >
            <FadeSlide direction="up" durationFrames={10}>
              <div
                style={{
                  backgroundColor: accentColor,
                  color: "#000",
                  fontFamily: BRAND.fontSans,
                  fontSize: 36,
                  fontWeight: 800,
                  padding: "12px 28px",
                  borderRadius: 10,
                  letterSpacing: "-0.005em",
                  textAlign: "center",
                  maxWidth: "85%",
                }}
              >
                {caption}
              </div>
            </FadeSlide>
          </AbsoluteFill>
        </Sequence>
      )}
    </AbsoluteFill>
  );
};

export const BRollMontageScene: React.FC<Props> = ({
  images,
  captions,
  frames_per_image,
  title,
  accentColor,
  durationFrames,
}) => {
  const perImage = frames_per_image
    ? frames_per_image
    : Math.max(15, Math.floor(durationFrames / images.length));

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background }}>
      {/* Series of images, each slightly overlapping the previous */}
      {images.map((src, i) => (
        <Sequence key={i} from={i * perImage} durationInFrames={perImage + 4} layout="none">
          <MontageImage
            src={src}
            caption={captions[i]}
            durationFrames={perImage}
            accentColor={accentColor}
            index={i}
          />
        </Sequence>
      ))}

      {/* Optional title chip pinned to top */}
      {title && (
        <AbsoluteFill
          style={{
            display: "flex",
            justifyContent: "flex-start",
            alignItems: "flex-start",
            padding: BRAND.padding.slide,
          }}
        >
          <MaskReveal direction="left">
            <div
              style={{
                backgroundColor: "rgba(0,0,0,0.65)",
                border: `2px solid ${accentColor}`,
                color: BRAND.textPrimary,
                fontFamily: BRAND.fontMono,
                fontSize: BRAND.fontSize.label,
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                padding: "10px 22px",
                borderRadius: 8,
              }}
            >
              {title}
            </div>
          </MaskReveal>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
