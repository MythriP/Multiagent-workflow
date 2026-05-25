// StatementOverlay — Phase C feature.
//
// While most narration is rendered word-by-word by PillCaption (a small
// translucent scrim hugging the active word), certain beats — the
// reel's punchline / declarative thesis lines — get a different
// treatment: the WHOLE phrase appears at once, big and bold, with NO
// pill background, anchored to a corner. The per-word pill is
// suppressed for those frames.
//
// Reference: Riley Brown / reactive-creator style "I SEE IT A BIT
// DIFFERENTLY" treatment. Big white uppercase Archivo Black, raw on
// the video.
//
// Anchoring:
//   • "top_right"     — anchored to the upper-right of the canvas.
//   • "bottom_left"   — anchored to the lower-left of the canvas.
// The active anchor is set per-segment by the Python pipeline (vibe
// default + per-scene override — e.g. avatar present → top_right).

import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MixedTypeText } from "./MixedTypeText";

export type StatementSegment = {
  /** The full phrase to show (typically one beat's narration). */
  text: string;
  /** Start / end seconds within the reel timeline. */
  start: number;
  end: number;
  /** Where to anchor the phrase. Decided by the Python pipeline. */
  anchor: "top_right" | "bottom_left";
  /** Optional words inside `text` to italicize (Fraunces accent). */
  italic_words?: string[];
};

type Props = {
  segments?: StatementSegment[];
  /** Accent color used for italic accent words. */
  accentColor?: string;
  /** Default text color. */
  textColor?: string;
};

const CANVAS_W = 1080;
const CANVAS_H = 1920;
const SAFE_MARGIN = 80;

export const StatementOverlay: React.FC<Props> = ({
  segments = [],
  accentColor = "#FFE066",
  textColor = "#FFFFFF",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const active = segments.find((s) => t >= s.start && t < s.end);
  if (!active) return null;

  // Local frame relative to this segment's start. Used for the snap-in
  // and snap-out animations.
  const segFrame = (t - active.start) * fps;
  const segDurationFrames = Math.max(1, (active.end - active.start) * fps);

  // Snap-in (first ~12 frames) — opposing-direction slide from the
  // canvas edge the phrase is anchored to. top_right slides in from the
  // right, bottom_left slides in from the left.
  const entry = spring({
    frame: segFrame,
    fps,
    config: { damping: 14, stiffness: 220, mass: 0.6 },
  });
  const slideXFrom =
    active.anchor === "top_right" ? 160 : -160;
  const slideX = interpolate(entry, [0, 1], [slideXFrom, 0]);

  // Snap-out on the last ~10 frames so the phrase clears before the
  // next scene starts.
  const exit = interpolate(
    segFrame,
    [segDurationFrames - 10, segDurationFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = entry * exit;

  // Layout: the phrase block is ~75% of canvas width so 2-line wraps look
  // balanced. Right-aligned for top_right, left-aligned for bottom_left.
  const blockMaxWidth = Math.round(CANVAS_W * 0.78);
  const isTopRight = active.anchor === "top_right";

  // Auto-scale font size based on word count so longer statements don't
  // overflow the canvas. The Python pipeline already skips beats >14
  // words (they fall back to PillCaption), but this provides a safety
  // net for edge cases and lets future tweaks raise the Python cap
  // without immediately breaking the visual.
  //   ≤ 8 words  → 108 px  (original punchy hero text)
  //   9–12 words → 88 px
  //   13–18 words → 68 px
  //   19+ words  → 52 px
  const wordCount = active.text.trim().split(/\s+/).length;
  let fontSize = 108;
  let letterSpacing = -2.5;
  if (wordCount > 18) {
    fontSize = 52;
    letterSpacing = -1.2;
  } else if (wordCount > 12) {
    fontSize = 68;
    letterSpacing = -1.6;
  } else if (wordCount > 8) {
    fontSize = 88;
    letterSpacing = -2.0;
  }

  const wrapperStyle: React.CSSProperties = isTopRight
    ? {
        position: "absolute",
        top: SAFE_MARGIN + 60,
        right: SAFE_MARGIN,
        maxWidth: blockMaxWidth,
        transform: `translateX(${slideX}px)`,
        opacity,
        pointerEvents: "none",
      }
    : {
        position: "absolute",
        bottom: SAFE_MARGIN + 200, // clear of the global subtitle area
        left: SAFE_MARGIN,
        maxWidth: blockMaxWidth,
        transform: `translateX(${slideX}px)`,
        opacity,
        pointerEvents: "none",
      };

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={wrapperStyle}>
        <MixedTypeText
          text={active.text}
          italicWords={active.italic_words ?? []}
          size={fontSize}
          color={textColor}
          italicColor={accentColor}
          letterSpacing={letterSpacing}
          lineHeight={1.0}
          align={isTopRight ? "right" : "left"}
          uppercaseSans
        />
      </div>
    </AbsoluteFill>
  );
};

// Avoid unused-var lint for CANVAS_H — exported for downstream callers
// that compute layout against the canvas height.
export const STATEMENT_CANVAS_H = CANVAS_H;
