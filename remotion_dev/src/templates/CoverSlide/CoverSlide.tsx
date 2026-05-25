import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";
import { BRAND } from "../../brand";
import { AccountLogo } from "../../components/AccountLogo";
import { AccentText } from "../../components/AccentText";

export const coverSlideSchema = z.object({
  // The main hook headline (ALL CAPS recommended for impact)
  headline: z.string(),
  // Words within the headline to colorize with accent color
  accentWords: z.array(z.string()).default([]),
  // Small tagline text below headline (e.g. "THE LINE BETWEEN SAFETY AND VULNERABILITY JUST GOT THINNER")
  tagline: z.string().default(""),
  // Path to hero image — use staticFile() path or remote URL
  heroImage: z.string(),
  // "SWIPE" or "NEXT →" — shown in the CTA pill
  ctaLabel: z.string().default("SWIPE"),
  // Override accent color per-post if needed
  accentColor: z.string().default(BRAND.accent),
});

export type CoverSlideProps = z.infer<typeof coverSlideSchema>;

export const CoverSlide: React.FC<CoverSlideProps> = ({
  headline,
  accentWords,
  tagline,
  heroImage,
  ctaLabel,
  accentColor,
}) => {
  const p = BRAND.padding.slide;

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background, fontFamily: BRAND.fontSans }}>

      {/* ── Hero image (full bleed, top ~62%) ── */}
      <div style={{ position: "absolute", inset: 0, height: "63%" }}>
        <Img
          src={heroImage}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center top",
          }}
        />
        {/* Bottom gradient so text reads cleanly over image */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "55%",
            background:
              "linear-gradient(to bottom, transparent 0%, rgba(10,10,10,0.7) 60%, #0A0A0A 100%)",
          }}
        />
      </div>

      {/* ── Account logo — top left ── */}
      <div style={{ position: "absolute", top: p, left: p }}>
        <AccountLogo glowColor={accentColor} />
      </div>

      {/* ── Bottom text block ── */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          padding: `0 ${p}px ${p}px`,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {/* Headline */}
        <div style={{ lineHeight: 1.12 }}>
          <AccentText
            text={headline}
            accentWords={accentWords}
            fontSize={BRAND.fontSize.coverHeadline}
            accentColor={accentColor}
            fontWeight={800}
            lineHeight={1.12}
          />
        </div>

        {/* Tagline + CTA row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          {/* Tagline */}
          {tagline ? (
            <span
              style={{
                fontFamily: BRAND.fontMono,
                fontSize: BRAND.fontSize.coverTagline,
                color: BRAND.textMuted,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                flex: 1,
              }}
            >
              {tagline}
            </span>
          ) : (
            <div style={{ flex: 1 }} />
          )}

          {/* SWIPE / NEXT pill */}
          <div
            style={{
              backgroundColor: accentColor,
              color: "#000",
              fontFamily: BRAND.fontMono,
              fontSize: 26,
              fontWeight: 700,
              letterSpacing: "0.06em",
              paddingTop: 12,
              paddingBottom: 12,
              paddingLeft: 28,
              paddingRight: 28,
              borderRadius: 8,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {ctaLabel} →
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
