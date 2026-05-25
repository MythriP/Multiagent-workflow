import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";
import { BRAND } from "../../brand";
import { AccountLogo } from "../../components/AccountLogo";
import { AccentText } from "../../components/AccentText";

export const closerSlideSchema = z.object({
  // The closing lines — punchline, CTA, key takeaway
  lines: z.array(z.string()),
  // Words to accent in the closer text
  accentWords: z.array(z.string()).default([]),
  // Optional card image at bottom (brand logo, newsletter screenshot, product card)
  cardImage: z.string().optional(),
  // Accent color override per post
  accentColor: z.string().default(BRAND.accent),
});

export type CloserSlideProps = z.infer<typeof closerSlideSchema>;

export const CloserSlide: React.FC<CloserSlideProps> = ({
  lines,
  accentWords,
  cardImage,
  accentColor,
}) => {
  const p = BRAND.padding.slide;
  const hasCard = !!cardImage;

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background, fontFamily: BRAND.fontSans }}>

      {/* ── Closing text block ── */}
      <div
        style={{
          position: "absolute",
          top: p,
          left: p,
          right: p,
          bottom: hasCard ? "48%" : p + 80,
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          gap: 0,
        }}
      >
        {lines.map((line, i) => {
          const isEmptyLine = line.trim() === "";

          if (isEmptyLine) {
            return <div key={i} style={{ height: BRAND.fontSize.closerText * 0.6 }} />;
          }

          return (
            <div key={i} style={{ marginBottom: BRAND.fontSize.closerText * 0.55 }}>
              <AccentText
                text={line}
                accentWords={accentWords}
                fontSize={BRAND.fontSize.closerText}
                accentColor={accentColor}
                fontWeight={400}
                lineHeight={1.35}
              />
            </div>
          );
        })}
      </div>

      {/* ── Card image — bottom (optional) ── */}
      {hasCard && (
        <div
          style={{
            position: "absolute",
            bottom: p,
            left: p,
            right: p,
            height: "43%",
            borderRadius: 20,
            overflow: "hidden",
            border: `1px solid ${BRAND.border}`,
            backgroundColor: BRAND.backgroundCard,
          }}
        >
          <Img
            src={cardImage!}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              objectPosition: "center",
            }}
          />
        </div>
      )}

      {/* ── Account logo — bottom left (only when no card) ── */}
      {!hasCard && (
        <div style={{ position: "absolute", bottom: p, left: p }}>
          <AccountLogo glowColor={accentColor} />
        </div>
      )}

      {/* ── Logo overlaid on card when card present ── */}
      {hasCard && (
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

      {/* ── Subtle accent line at top ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: `linear-gradient(to right, ${accentColor}, transparent)`,
          opacity: 0.6,
        }}
      />
    </AbsoluteFill>
  );
};
