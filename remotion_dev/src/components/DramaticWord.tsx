import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { VibeProfile } from "../DynamicReel";
import { MixedTypeText } from "./MixedTypeText";
import { isVideoSrc, resolveSrc } from "../scenes/_mediaHelpers";

type Props = {
  text: string;
  /** Legacy variant prop. Kept for back-compat; the Phase B layout
   *  always uses MixedTypeText (italic Fraunces + Archivo Black). */
  variant?: "italic-serif" | "bold-sans";
  background?: string;
  textColor?: string;
  /** Optional background media. Renders full-canvas behind the word.
   *  Image or video file. */
  bgMediaSrc?: string;
  vibe?: VibeProfile | null;
};

/**
 * DramaticWord — Phase B rebuild.
 *
 * Layout: a single short editorial phrase pinned to the TOP-RIGHT of the
 * canvas (no longer center). The background fills the entire canvas —
 * either the bg_media (Pexels b-roll / Veo clip) or the vibe primary_bg.
 *
 * Why top-right: it pairs naturally with the global PillCaption at the
 * bottom (or seam at y=960 in split-screen mode), giving a Newsroom /
 * Twitch-overlay feel rather than the centered "PowerPoint slide" look
 * of the previous typewriter treatment.
 *
 * Motion: the phrase snap-slides in from the right (opposing the global
 * PillCaption which is anchored bottom-center), holds for the dwell, and
 * snap-slides out on the final frames. No textShadow, no glow. Italic
 * accents come for free via MixedTypeText.
 *
 * IMPORTANT: this component is throttled by Python to max 1 occurrence
 * per reel, and only emitted when the active vibe flags
 * `allow_dramatic_word: true`. See scene_writer._cap_dramatic_word.
 */
export const DramaticWord: React.FC<Props> = ({
  text,
  background = "#0a0a0a",
  textColor = "#ffffff",
  bgMediaSrc,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Resolve effective colors from the vibe (vibe wins). Without a vibe
  // we fall back to the per-call props, which themselves default to a
  // dark surface / white text.
  const effectiveBg = vibe?.color_palette.primary_bg ?? background;
  const effectiveText = vibe?.color_palette.text_primary ?? textColor;
  const accent = vibe?.color_palette.accent ?? textColor;

  // Pick italic words: every other word feels too busy, so we italicize
  // the LAST word only — that's where the punch usually lands. Falls
  // back to italicizing the whole phrase if there's only one word.
  const tokens = text.trim().split(/\s+/);
  const italicWords =
    tokens.length > 1 ? [tokens[tokens.length - 1]] : tokens;

  // Snap-slide entry from the right (opposing global subtitle which
  // springs from below). Holds for the middle 70% of the duration.
  const entry = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 220, mass: 0.6 },
  });
  const exit = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const slideX = interpolate(entry, [0, 1], [180, 0]);
  const opacity = entry * exit;

  return (
    <AbsoluteFill style={{ background: effectiveBg, overflow: "hidden" }}>
      {/* Full-canvas background media. No blur, no scrim — the word lives
          on top-right where the bg is least likely to clash. */}
      {bgMediaSrc ? (
        isVideoSrc(bgMediaSrc) ? (
          <OffthreadVideo
            src={resolveSrc(bgMediaSrc)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <Img
            src={resolveSrc(bgMediaSrc)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )
      ) : null}

      {/* Top-right editorial phrase. Width capped at 70% of the canvas so
          long phrases wrap to 2 lines (instead of overflowing the right
          edge), and right-aligned so the text "hangs" off the corner. */}
      <div
        style={{
          position: "absolute",
          top: 160,
          right: 60,
          maxWidth: 760,
          transform: `translateX(${slideX}px)`,
          opacity,
          pointerEvents: "none",
        }}
      >
        <MixedTypeText
          text={text}
          italicWords={italicWords}
          size={132}
          color={effectiveText}
          italicColor={accent}
          letterSpacing={-3}
          lineHeight={0.98}
          align="right"
          uppercaseSans
        />
      </div>
    </AbsoluteFill>
  );
};
