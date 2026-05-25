import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { VibeProfile } from "../../DynamicReel";

const { fontFamily } = loadFont();

type Props = {
  kicker: string;
  headline: string;
  subhead?: string;
  source?: string;
  accentColor?: string;
  /** Supporting image rendered behind a frosted dark wash. */
  bgImage?: string;
  /** Ambient Pexels backdrop, full-bleed blurred. */
  bgMediaSrc?: string;
  vibe?: VibeProfile | null;
};

const TC_GREEN = "#0E9F4F";

export const HeadlineCard: React.FC<Props> = ({
  kicker,
  headline,
  subhead,
  source = "Source",
  accentColor = TC_GREEN,
  bgImage,
  bgMediaSrc,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const kickerReveal = spring({ frame, fps, config: { damping: 14, stiffness: 130 } });
  const headlineReveal = spring({ frame: frame - 8, fps, config: { damping: 12, stiffness: 100, mass: 0.6 } });
  const subheadReveal = spring({ frame: frame - 30, fps, config: { damping: 14, stiffness: 110 } });

  const resolveBg = (src: string): string => {
    if (
      src.startsWith("data:") ||
      src.startsWith("http://") ||
      src.startsWith("https://") ||
      src.startsWith("/")
    ) {
      return src;
    }
    return staticFile(src);
  };
  const isVideoBg = (src: string): boolean => {
    const lowered = src.split("?")[0].toLowerCase();
    if (lowered.startsWith("data:video/")) return true;
    return /\.(mp4|webm|mov|m4v)$/.test(lowered);
  };

  // Visual mode: with the vibe profile, the headline always lives on the
  // vibe palette. bgImage / bgMediaSrc still scrim under the text when set.
  const vibeBg = vibe?.color_palette.primary_bg ?? "#0a0a0a";
  const vibeText = vibe?.color_palette.text_primary ?? "#ffffff";
  const isDark = true;
  const headlineColor = vibeText;
  const subheadColor = `${vibeText}d9`; // ~85% alpha
  const sourceColor = `${vibeText}b3`;  // ~70% alpha

  return (
    <AbsoluteFill
      style={{
        background: bgImage || bgMediaSrc ? "#000" : vibeBg,
        flexDirection: "column",
        // Top-anchored so the avatar bust has the bottom 800px clear. The
        // accent bar at top, then kicker → headline → subhead all stack
        // from the top.
        justifyContent: "flex-start",
        paddingTop: 220,
        paddingLeft: 80,
        paddingRight: 80,
        paddingBottom: 80,
        gap: 32,
        overflow: "hidden",
      }}
    >
      {bgImage ? (
        <>
          {/* Crisp foreground image, full-bleed cover crop. No blurred
              ambient layer — the no-gradient/flat rule forbids it. */}
          <AbsoluteFill>
            <Img
              src={bgImage}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
          </AbsoluteFill>
          {/* Solid scrim for legibility (was a gradient, now a flat tint). */}
          <AbsoluteFill style={{ background: "rgba(0,0,0,0.65)" }} />
        </>
      ) : bgMediaSrc ? (
        <>
          <AbsoluteFill>
            {isVideoBg(bgMediaSrc) ? (
              <OffthreadVideo
                src={resolveBg(bgMediaSrc)}
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <Img
                src={resolveBg(bgMediaSrc)}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            )}
          </AbsoluteFill>
          <AbsoluteFill style={{ background: "rgba(0,0,0,0.65)" }} />
        </>
      ) : null}

      {/* Top accent bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          height: 16,
          width: "100%",
          background: accentColor,
        }}
      />

      {/* Kicker */}
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 36,
          color: accentColor,
          letterSpacing: 4,
          textTransform: "uppercase",
          opacity: kickerReveal,
          transform: `translateY(${interpolate(kickerReveal, [0, 1], [-20, 0])}px)`,
        }}
      >
        {kicker}
      </div>

      {/* Headline — multiline, bold */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 110,
          color: headlineColor,
          letterSpacing: -3,
          lineHeight: 1.05,
          opacity: headlineReveal,
          transform: `translateY(${interpolate(headlineReveal, [0, 1], [40, 0])}px)`,
        }}
      >
        {headline}
      </div>

      {/* Subhead */}
      {subhead && (
        <div
          style={{
            fontFamily,
            fontWeight: 600,
            fontSize: 50,
            color: subheadColor,
            letterSpacing: -0.5,
            lineHeight: 1.25,
            opacity: subheadReveal,
            transform: `translateY(${interpolate(subheadReveal, [0, 1], [20, 0])}px)`,
          }}
        >
          {subhead}
        </div>
      )}

      {/* Source — bottom right */}
      <div
        style={{
          position: "absolute",
          bottom: 60,
          right: 60,
          fontFamily,
          fontWeight: 700,
          fontSize: 28,
          color: sourceColor,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          opacity: interpolate(frame, [40, 60], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        Source: {source}
      </div>
    </AbsoluteFill>
  );
};
