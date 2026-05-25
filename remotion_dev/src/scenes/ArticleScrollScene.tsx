import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

/**
 * Scaled article image is 1080 wide × ~7125 tall.
 * Each "stop" is a Y position (top edge of the rendered image, in reel coords)
 * such that the highlighted sentence sits in the upper-third of the viewport.
 */
export type Stop = {
  /** Frame at which this stop is reached (after scrolling from previous) */
  frameAtStop: number;
  /** Frame at which we start scrolling AWAY (i.e. "hold" length) */
  frameLeaveStop: number;
  /** Y translate for the article image (negative = scrolled down through article) */
  scrollY: number;
  /** Highlight box in REEL coordinates (after the scroll has been applied) */
  highlight?: {
    /** X position from left of viewport */
    x: number;
    /** Y position from top of viewport */
    y: number;
    width: number;
    height: number;
  };
  /** Caption text shown at the bottom while at this stop */
  caption: string;
  /** Words in the caption to color with the accent */
  accentWords?: string[];
};

type Props = {
  imageSrc: string;
  stops: Stop[];
  /** Brand color sampled from the article (TechCrunch green) */
  accentColor?: string;
  /** Highlight color (text-selection yellow) */
  highlightColor?: string;
};

const ARTICLE_GREEN = "#0E9F4F";
const SELECTION_YELLOW = "#FFF066";

/** Smooth easing for scroll between two stops */
const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export const ArticleScrollScene: React.FC<Props> = ({
  imageSrc,
  stops,
  accentColor = ARTICLE_GREEN,
  highlightColor = SELECTION_YELLOW,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Compute current scrollY by interpolating between stops
  let scrollY = stops[0].scrollY;
  let activeStopIdx = 0;

  for (let i = 0; i < stops.length; i++) {
    const stop = stops[i];
    const next = stops[i + 1];

    if (frame < stop.frameAtStop) {
      // Still scrolling INTO this stop from the previous
      const prev = stops[i - 1] || stop;
      const startFrame = prev.frameLeaveStop;
      const endFrame = stop.frameAtStop;
      const t = (frame - startFrame) / Math.max(1, endFrame - startFrame);
      const eased = easeInOutCubic(Math.max(0, Math.min(1, t)));
      scrollY = prev.scrollY + (stop.scrollY - prev.scrollY) * eased;
      activeStopIdx = i - 1 >= 0 ? i - 1 : 0;
      break;
    } else if (frame >= stop.frameAtStop && frame <= stop.frameLeaveStop) {
      // Holding at this stop
      scrollY = stop.scrollY;
      activeStopIdx = i;
      break;
    } else if (next && frame > stop.frameLeaveStop && frame < next.frameAtStop) {
      // Scrolling toward next stop
      const t = (frame - stop.frameLeaveStop) / (next.frameAtStop - stop.frameLeaveStop);
      const eased = easeInOutCubic(t);
      scrollY = stop.scrollY + (next.scrollY - stop.scrollY) * eased;
      activeStopIdx = i;
      break;
    } else if (!next && frame > stop.frameLeaveStop) {
      // Past the last stop
      scrollY = stop.scrollY;
      activeStopIdx = i;
    }
  }

  const activeStop = stops[activeStopIdx];

  // Highlight only animates IN once we're holding at the stop
  const isAtStop = frame >= activeStop.frameAtStop && frame <= activeStop.frameLeaveStop;
  const framesIntoHold = frame - activeStop.frameAtStop;
  const highlightReveal = isAtStop
    ? spring({
        frame: framesIntoHold,
        fps,
        config: { damping: 14, stiffness: 180, mass: 0.5 },
      })
    : 0;

  const captionWords = activeStop.caption.split(/\s+/);

  return (
    <AbsoluteFill style={{ backgroundColor: "#fff", overflow: "hidden" }}>
      {/* The scrolling article */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 1080,
          transform: `translateY(${-scrollY}px)`,
          willChange: "transform",
        }}
      >
        <Img
          src={imageSrc}
          style={{
            width: 1080,
            height: "auto",
            display: "block",
          }}
        />

        {/* Highlight overlay positioned in ARTICLE coords (so it scrolls with text) */}
        {activeStop.highlight && (
          <div
            style={{
              position: "absolute",
              left: activeStop.highlight.x,
              top: activeStop.highlight.y + scrollY, // back-compensate to put it in article coords
              width: activeStop.highlight.width,
              height: activeStop.highlight.height,
              background: highlightColor,
              opacity: highlightReveal * 0.55,
              borderRadius: 4,
              transformOrigin: "left center",
              transform: `scaleX(${highlightReveal})`,
              mixBlendMode: "multiply",
              boxShadow: isAtStop
                ? `0 0 0 2px ${highlightColor}, 0 0 24px ${highlightColor}88`
                : "none",
            }}
          />
        )}
      </div>

      {/* Bottom caption bar with gradient */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 480,
          background:
            "linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.85) 50%, rgba(0,0,0,0) 100%)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "absolute",
          bottom: 110,
          left: 0,
          right: 0,
          padding: "0 60px",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "12px 20px",
          fontFamily,
        }}
      >
        {captionWords.map((word, i) => {
          const wordStart = activeStop.frameAtStop + Math.floor(i * 2.5);
          const reveal = spring({
            frame: frame - wordStart,
            fps,
            config: { damping: 12, stiffness: 240, mass: 0.4 },
          });
          const opacity = interpolate(frame, [wordStart, wordStart + 4], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const isAccent = activeStop.accentWords?.some((aw) =>
            word.toLowerCase().includes(aw.toLowerCase())
          );

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                fontSize: 84,
                fontWeight: 900,
                color: isAccent ? accentColor : "white",
                textTransform: "uppercase",
                letterSpacing: -1.5,
                lineHeight: 1.05,
                transform: `translateY(${interpolate(reveal, [0, 1], [24, 0])}px)`,
                opacity,
                textShadow: isAccent
                  ? `0 0 24px ${accentColor}aa, 0 4px 16px rgba(0,0,0,0.85)`
                  : "0 4px 16px rgba(0,0,0,0.85)",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>

      {/* TechCrunch source badge — top right, small, classy */}
      <div
        style={{
          position: "absolute",
          top: 60,
          right: 50,
          fontFamily,
          fontSize: 26,
          fontWeight: 800,
          color: "white",
          letterSpacing: 2,
          textTransform: "uppercase",
          background: accentColor,
          padding: "10px 20px",
          borderRadius: 6,
          boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
        }}
      >
        TechCrunch
      </div>
    </AbsoluteFill>
  );
};
