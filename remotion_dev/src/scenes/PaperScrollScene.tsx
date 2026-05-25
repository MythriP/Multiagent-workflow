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

type Props = {
  /** Tall image source — typically a multi-page rendered PDF (1080w × NNNNNh). */
  imageSrc: string;
  /** Caption shown at bottom (word-by-word) */
  caption?: string;
  /** Optional source label, top-right */
  source?: string;
  /** Accent color used for highlight glow + key words in the caption */
  accentColor?: string;
};

/**
 * "Scroll through the paper" effect.
 *
 * Renders a tall image (e.g. a full PDF rendered as one PNG) and animates
 * its translateY from 0 to -(imgHeight - viewportHeight) across the scene,
 * with a subtle ease so the camera lingers at the start and end.
 *
 * We don't know the image height ahead of time at render parse-time, so we
 * use Img's `onLoad` to capture it, fall back to a sensible default, and
 * smoothly catch up once we know the real height.
 */
export const PaperScrollScene: React.FC<Props> = ({
  imageSrc,
  caption = "",
  source,
  accentColor = "#FFE066",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Use a state-less approach: we set CSS variables based on aspect ratio
  // assumed from a rendered 1080w PDF (typically ~14000px tall for ~14 pages).
  // The image is rendered absolutely positioned, so even if our guess is
  // slightly off the visible scroll still spans most of the paper.
  const VIEWPORT_W = 1080;
  const VIEWPORT_H = 1920;
  const ESTIMATED_TALL_H = 14000;

  // Total scroll distance (negative translateY)
  const maxScroll = -(ESTIMATED_TALL_H - VIEWPORT_H);

  // Eased scroll progress: hold at top for ~5%, scroll most of the way,
  // hold at the end for ~5%.
  const t = frame / Math.max(1, durationInFrames);
  const eased =
    t < 0.05
      ? 0
      : t > 0.95
      ? 1
      : (t - 0.05) / 0.9;

  const scrollY = maxScroll * eased;

  // Subtle entry / exit fade
  const entryOpacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });
  const exitOpacity = interpolate(
    frame,
    [durationInFrames - 8, durationInFrames],
    [1, 0.85],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Periodic highlight pulses to draw the eye to "what's being read"
  const pulse = (Math.sin(frame * 0.18) + 1) / 2; // 0..1
  const highlightOpacity = 0.18 + pulse * 0.12;

  const words = caption.split(/\s+/).filter(Boolean);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a", overflow: "hidden" }}>
      {/* Solid paper backdrop (was radial-gradient). */}

      {/* The scrolling paper */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          width: VIEWPORT_W * 0.92,
          transform: `translateX(-50%) translateY(${scrollY}px)`,
          willChange: "transform",
          opacity: entryOpacity * exitOpacity,
          borderRadius: 6,
          overflow: "hidden",
        }}
      >
        <Img
          src={imageSrc}
          style={{
            width: "100%",
            height: "auto",
            display: "block",
          }}
        />
      </div>

      {/* Animated highlight band — draws focus to the upper third of the
          viewport where readers naturally look */}
      <div
        style={{
          position: "absolute",
          top: VIEWPORT_H * 0.32,
          left: 80,
          right: 80,
          height: 90,
          background: accentColor,
          opacity: highlightOpacity,
          mixBlendMode: "overlay",
          borderRadius: 4,
          pointerEvents: "none",
        }}
      />

      {/* Bottom dark wash for caption legibility (was a gradient; now a
          flat tinted rectangle at the bottom third). */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: VIEWPORT_H * 0.32,
          background: "rgba(0,0,0,0.78)",
          pointerEvents: "none",
        }}
      />

      {/* Caption */}
      {words.length > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 160,
            left: 0,
            right: 0,
            padding: "0 60px",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "10px 18px",
            fontFamily,
          }}
        >
          {words.map((word, i) => {
            const wordStart = Math.floor(
              (i / Math.max(1, words.length)) *
                Math.min(durationInFrames * 0.55, 36)
            );
            const reveal = spring({
              frame: frame - wordStart,
              fps,
              config: { damping: 11, stiffness: 240, mass: 0.4 },
            });
            const opacity = interpolate(
              frame,
              [wordStart, wordStart + 4],
              [0, 1],
              { extrapolateRight: "clamp" }
            );
            const isAccent = /\d|paper|model|score|state-of-the-art|sota/i.test(
              word
            );
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  fontSize: 78,
                  fontWeight: 900,
                  color: isAccent ? accentColor : "white",
                  textTransform: "uppercase",
                  letterSpacing: -1.5,
                  lineHeight: 1.05,
                  transform: `translateY(${interpolate(reveal, [0, 1], [24, 0])}px)`,
                  opacity,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
      )}

      {/* Source badge */}
      {source ? (
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
            background: "rgba(0,0,0,0.65)",
            border: `1px solid ${accentColor}88`,
            padding: "10px 20px",
            borderRadius: 6,
          }}
        >
          {source}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
