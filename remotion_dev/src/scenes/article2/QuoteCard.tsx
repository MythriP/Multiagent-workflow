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

const { fontFamily } = loadFont();

type Props = {
  text: string;
  /** Words to highlight in the accent color */
  highlight?: string[];
  accentColor?: string;
  background?: string;
  /** Optional ambient backdrop (typically a Pexels b-roll clip).
   *  When provided, replaces the flat `background` color with a
   *  full-bleed blurred video and a dark scrim under the quote. */
  bgMediaSrc?: string;
};

const TC_GREEN = "#0E9F4F";

/**
 * Decide whether a CSS color string is "light" enough that we need dark
 * text on top, or dark enough that we need light text. Handles named
 * shades, #fff, #ffffff, rgb(), rgba(). Defaults to "dark" for anything
 * we can't parse — which keeps us aligned with the project's overall
 * dark aesthetic if the LLM emits something exotic.
 */
function isLightBackground(bg: string): boolean {
  if (!bg) return false;
  const s = bg.trim().toLowerCase();
  // Named colors that are unambiguously light
  if (["white", "ivory", "snow", "ghostwhite", "azure", "mintcream"].includes(s)) {
    return true;
  }
  // #f / #fff / #ffffff family — any 3 / 6 hex where R, G, B all > 200
  const hexMatch = s.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hexMatch) {
    let h = hexMatch[1];
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return r > 200 && g > 200 && b > 200;
  }
  // rgb(...) / rgba(...)
  const rgbMatch = s.match(/^rgba?\(([^)]+)\)$/);
  if (rgbMatch) {
    const parts = rgbMatch[1].split(",").map((p) => parseFloat(p.trim()));
    if (parts.length >= 3) {
      return parts[0] > 200 && parts[1] > 200 && parts[2] > 200;
    }
  }
  return false;
}

export const QuoteCard: React.FC<Props> = ({
  text,
  highlight = [],
  accentColor = TC_GREEN,
  // Default is now dark to match the rest of the video aesthetic. The
  // auto-contrast check below still handles light backgrounds correctly
  // if the LLM emits one.
  background = "#0a0a0a",
  bgMediaSrc,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = text.split(/(\s+)/); // keep whitespace

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

  // When a Pexels backdrop is provided we always render in dark mode —
  // text white over a blurred video + dark scrim.
  const hasBgMedia = !!bgMediaSrc;
  const isLight = !hasBgMedia && isLightBackground(background);
  const textColor = isLight ? "#0a0a0a" : "#ffffff";
  const highlightColor = accentColor;

  return (
    <AbsoluteFill
      style={{
        // When a Pexels backdrop is active, paint pure black underneath
        // so any letterboxed area still looks intentional. Otherwise use
        // the explicit `background` color (defaults to #0a0a0a).
        background: hasBgMedia ? "#000" : background,
        flexDirection: "column",
        // Top-anchored so the avatar bust + subtitle pill have the bottom
        // half of the canvas. The big quote mark sits in the corner and
        // the quoted text starts ~280px from the top.
        justifyContent: "flex-start",
        paddingTop: 280,
        paddingLeft: 90,
        paddingRight: 90,
      }}
    >
      {hasBgMedia && bgMediaSrc ? (
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
          {/* Solid scrim (no gradient, no blurred ambient layer). */}
          <AbsoluteFill style={{ background: "rgba(0,0,0,0.65)" }} />
        </>
      ) : null}

      {/* Big quote mark */}
      <div
        style={{
          position: "absolute",
          top: 70,
          left: 80,
          fontFamily: "Georgia, serif",
          fontSize: 320,
          color: accentColor,
          opacity: 0.15,
          lineHeight: 0.8,
        }}
      >
        “
      </div>

      {/* Quote */}
      <div
        style={{
          fontFamily,
          fontSize: 92,
          fontWeight: 800,
          color: textColor,
          letterSpacing: -1.5,
          lineHeight: 1.18,
        }}
      >
        {words.map((w, i) => {
          if (/^\s+$/.test(w)) return <span key={i}>{w}</span>;
          const cleanWord = w.toLowerCase().replace(/[^a-z0-9$×]/g, "");
          const isHighlighted = highlight.some((h) => cleanWord.includes(h.toLowerCase()));
          const wordIdx = words.slice(0, i).filter((s) => !/^\s+$/.test(s)).length;
          const start = wordIdx * 3;
          const reveal = spring({
            frame: frame - start,
            fps,
            config: { damping: 14, stiffness: 200, mass: 0.4 },
          });
          const opacity = interpolate(frame, [start, start + 4], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                color: isHighlighted ? highlightColor : textColor,
                background: isHighlighted ? `${highlightColor}22` : "transparent",
                padding: isHighlighted ? "0 12px" : "0",
                borderRadius: 8,
                opacity,
                transform: `translateY(${interpolate(reveal, [0, 1], [20, 0])}px)`,
              }}
            >
              {w}
            </span>
          );
        })}
      </div>

      {/* Bottom accent bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          height: 12,
          width: "100%",
          background: accentColor,
          transform: `scaleX(${interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" })})`,
          transformOrigin: "left",
        }}
      />
    </AbsoluteFill>
  );
};
