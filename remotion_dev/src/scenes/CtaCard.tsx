import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import { AmbientBackdrop } from "../components/AmbientBackdrop";
import type { VibeProfile } from "../DynamicReel";

const { fontFamily } = loadFont();

type Props = {
  text: string;
  /** Accent reserved for the arrow chevron; the headline itself is the
   *  vibe's text_primary color. */
  accentColor: string;
  /** Optional ambient blurred back layer. Off by default (CTA is meant to
   *  be the cleanest moment in the reel). */
  bgMediaSrc?: string;
  vibe?: VibeProfile | null;
};

/**
 * CTA card. By design this is dead-simple: black background, big white
 * sentence, sub-arrow that nudges down. The AvatarOverlay rides on top
 * (mounted by DynamicReel), so the host's bust is the focal element.
 *
 * No gradient. No emoji explosion. The point is "narrator looks at
 * camera, says one line, done."
 */
export const CtaCard: React.FC<Props> = ({ text, bgMediaSrc, accentColor, vibe }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pop = spring({
    frame,
    fps,
    config: { damping: 10, stiffness: 180, mass: 0.5 },
  });

  const arrowOpacity = interpolate(frame, [12, 28], [0, 1], {
    extrapolateRight: "clamp",
  });

  const bg = vibe?.color_palette.primary_bg ?? "#000000";
  const textColor = vibe?.color_palette.text_primary ?? "#ffffff";

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: 360,
      }}
    >
      {bgMediaSrc ? <AmbientBackdrop src={bgMediaSrc} opacity={0.32} scrim={0.7} /> : null}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          color: textColor,
          fontSize: 130,
          textAlign: "center",
          letterSpacing: -3.5,
          lineHeight: 1.05,
          maxWidth: 920,
          transform: `scale(${0.85 + pop * 0.15})`,
        }}
      >
        {text}
      </div>

      <div
        style={{
          fontFamily,
          color: accentColor,
          fontSize: 56,
          fontWeight: 700,
          marginTop: 48,
          opacity: arrowOpacity,
          letterSpacing: 4,
        }}
      >
        ↓
      </div>
    </AbsoluteFill>
  );
};
