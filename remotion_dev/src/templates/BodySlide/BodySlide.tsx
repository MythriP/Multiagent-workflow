import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";
import { BRAND } from "../../brand";
import { AccountLogo } from "../../components/AccountLogo";

export const bodySlideSchema = z.object({
  // Array of text lines/paragraphs. Each string is a separate paragraph block.
  // Supports ">" prefix for bullet-point style (e.g. "> anthropic builds a cyberweapon")
  lines: z.array(z.string()),
  // Optional image at the bottom half of the slide
  image: z.string().optional(),
  // Accent color for the logo glow
  accentColor: z.string().default(BRAND.accent),
});

export type BodySlideProps = z.infer<typeof bodySlideSchema>;

export const BodySlide: React.FC<BodySlideProps> = ({
  lines,
  image,
  accentColor,
}) => {
  const p = BRAND.padding.slide;
  const hasImage = !!image;

  // Text area takes more vertical space when there's no image
  const textAreaHeight = hasImage ? "50%" : "82%";
  const fontSize = hasImage
    ? BRAND.fontSize.bodyText
    : BRAND.fontSize.bodyTextLarge;

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background, fontFamily: BRAND.fontSans }}>

      {/* ── Text block ─────────────────────────────────────────────────
          - With image:    text sits in the top half, vertically centered there
          - Text-only:     text fills the slide and is vertically centered
      ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: textAreaHeight,
          padding: `${p}px ${p}px 0`,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          gap: 0,
        }}
      >
        {lines.map((line, i) => {
          const isBullet = line.startsWith("> ");
          const text = isBullet ? line.slice(2) : line;
          const isEmptyLine = line.trim() === "";

          if (isEmptyLine) {
            return <div key={i} style={{ height: fontSize * 0.6 }} />;
          }

          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: isBullet ? 16 : 0,
                marginBottom: isBullet ? 4 : fontSize * 0.55,
              }}
            >
              {isBullet && (
                <span
                  style={{
                    color: BRAND.textMuted,
                    fontSize,
                    lineHeight: 1.35,
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                >
                  &gt;
                </span>
              )}
              <p
                style={{
                  margin: 0,
                  padding: 0,
                  fontFamily: BRAND.fontSans,
                  fontSize,
                  fontWeight: 400,
                  color: BRAND.textPrimary,
                  lineHeight: 1.35,
                }}
              >
                {text}
              </p>
            </div>
          );
        })}
      </div>

      {/* ── Image — bottom section (only when image is provided) ── */}
      {hasImage && (
        <div
          style={{
            position: "absolute",
            bottom: p,
            left: p,
            right: p,
            height: "44%",
            borderRadius: 20,
            overflow: "hidden",
            border: `1px solid ${BRAND.border}`,
          }}
        >
          <Img
            src={image!}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
            }}
          />
        </div>
      )}

      {/* ── Account logo — bottom left ── */}
      <div
        style={{
          position: "absolute",
          bottom: p,
          left: p,
          ...(hasImage && { display: "none" }),
        }}
      >
        {!hasImage && <AccountLogo glowColor={accentColor} />}
      </div>

      {/* ── Logo on top of image when image present ── */}
      {hasImage && (
        <div
          style={{
            position: "absolute",
            bottom: p + 16,
            left: p + 16,
            zIndex: 10,
          }}
        >
          <AccountLogo size={42} glowColor={accentColor} />
        </div>
      )}

    </AbsoluteFill>
  );
};
