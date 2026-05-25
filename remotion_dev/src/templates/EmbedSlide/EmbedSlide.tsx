import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";
import { BRAND } from "../../brand";
import { AccountLogo } from "../../components/AccountLogo";

export const embedSlideSchema = z.object({
  // Optional short context text above the embed (1-3 lines max)
  contextText: z.string().optional(),
  // The embed image — screenshot of a tweet, news article, social post, chart, etc.
  embedImage: z.string(),
  // Optional caption below embed
  captionText: z.string().optional(),
  // Accent color for logo glow
  accentColor: z.string().default(BRAND.accent),
});

export type EmbedSlideProps = z.infer<typeof embedSlideSchema>;

export const EmbedSlide: React.FC<EmbedSlideProps> = ({
  contextText,
  embedImage,
  captionText,
  accentColor,
}) => {
  const p = BRAND.padding.slide;
  const hasContext = !!contextText;
  const hasCaption = !!captionText;

  // Dynamically size the embed card based on what's shown
  const topOffset = hasContext ? 220 : p;
  const bottomOffset = hasCaption ? 160 : p + 60;

  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background, fontFamily: BRAND.fontSans }}>

      {/* ── Context text — top (optional) ── */}
      {hasContext && (
        <div
          style={{
            position: "absolute",
            top: p,
            left: p,
            right: p,
          }}
        >
          <p
            style={{
              margin: 0,
              fontFamily: BRAND.fontSans,
              fontSize: BRAND.fontSize.embedText,
              fontWeight: 400,
              color: BRAND.textPrimary,
              lineHeight: 1.35,
            }}
          >
            {contextText}
          </p>
        </div>
      )}

      {/* ── Embed card — the screenshot/social post ── */}
      <div
        style={{
          position: "absolute",
          top: topOffset,
          bottom: bottomOffset,
          left: p,
          right: p,
          borderRadius: 20,
          overflow: "hidden",
          border: `1px solid ${BRAND.border}`,
          backgroundColor: BRAND.backgroundCard,
        }}
      >
        <Img
          src={embedImage}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            objectPosition: "top center",
          }}
        />
      </div>

      {/* ── Caption below embed (optional) ── */}
      {hasCaption && (
        <div
          style={{
            position: "absolute",
            bottom: p + 60,
            left: p,
            right: p,
          }}
        >
          <p
            style={{
              margin: 0,
              fontFamily: BRAND.fontSans,
              fontSize: 34,
              fontWeight: 400,
              color: BRAND.textMuted,
              lineHeight: 1.4,
            }}
          >
            {captionText}
          </p>
        </div>
      )}

      {/* ── Account logo — bottom left ── */}
      <div style={{ position: "absolute", bottom: p, left: p }}>
        <AccountLogo size={42} glowColor={accentColor} />
      </div>
    </AbsoluteFill>
  );
};
