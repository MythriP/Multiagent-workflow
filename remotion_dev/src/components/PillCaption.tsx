import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import staticCaptions from "../captions.json";

const { fontFamily } = loadFont();

export type PillWord = {
  text: string;
  start: number;
  end: number;
  line?: number;
  /** When true, this word belongs to a scene whose layout is a horizontal
   *  50/50 split. The pill should ride the seam (y=960) instead of being
   *  bottom-anchored, so it doesn't crash into either pane's content. */
  splitSeam?: boolean;
  /** When true, the pill caption is suppressed for this word — used during
   *  statement-mode windows where the entire phrase is being shown by
   *  StatementOverlay instead. The two are mutually exclusive. */
  suppress?: boolean;
};

type Props = {
  /**
   * Word-level timestamps to render. If omitted, falls back to the static
   * captions.json bundled in src/ (used by the legacy ArticleReel demo).
   */
  words?: PillWord[];
  /** Show only words within this seconds range (sceneStart..sceneEnd). */
  fromSec?: number;
  toSec?: number;
  /** Vertical position from bottom (px). */
  bottom?: number;
  /** Y coordinate of the seam used when a word has `splitSeam: true`. */
  seamY?: number;
  /** Words to highlight in accent color */
  accentWords?: string[];
  accentColor?: string;
  /** Legacy pill background color. Phase B retired the solid-pill look;
   *  the prop is accepted for back-compat with old callers but the
   *  component now always renders a transparent caption. */
  background?: string;
  /** Text color */
  textColor?: string;
  /** Pill font size */
  fontSize?: number;
  /** When true, render at ~75% size + 0.85 opacity. Used while the avatar
   *  bust is on screen so the subtitle pill doesn't fight the host. */
  compact?: boolean;
};

/**
 * Renders the CURRENT word being spoken as a single pill at the bottom of the
 * frame. Reads from the `words` prop (preferred) or the bundled captions.json
 * (legacy). Shows whichever word's [start..end] window contains the current
 * playhead time. This is the Riley Brown / Varun Mayya signature look:
 * ONE word at a time, perfectly synced.
 */
export const PillCaption: React.FC<Props> = ({
  words,
  fromSec = 0,
  toSec = Infinity,
  bottom = 240,
  seamY = 960,
  accentWords = [],
  accentColor = "#FFE066",
  background: _background = "#0a0a0a",
  textColor = "white",
  fontSize = 76,
  compact = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const allWords: PillWord[] = (words ?? (staticCaptions.words as PillWord[])).filter(
    (w) => w.start >= fromSec && w.end <= toSec
  );

  // Find current word (whose window contains t, with small lookahead)
  const current = allWords.find((w) => t >= w.start - 0.05 && t <= w.end + 0.08);
  if (!current) return null;

  // Suppression: statement-mode windows display the whole phrase via
  // StatementOverlay; the per-word pill goes silent for those frames so
  // the two captions never stack.
  if (current.suppress) return null;

  // Skip empty / pause tokens
  const cleaned = current.text.trim();
  if (!cleaned || /^\.{2,}$/.test(cleaned) || /^…+$/.test(cleaned)) return null;

  // Pop-in spring keyed off the word's start
  const wordFrame = (t - current.start) * fps;
  const reveal = spring({
    frame: wordFrame,
    fps,
    config: { damping: 11, stiffness: 280, mass: 0.4 },
  });

  const isAccent = accentWords.some((aw) =>
    cleaned
      .toLowerCase()
      .replace(/[^a-z0-9$×]/g, "")
      .includes(aw.toLowerCase())
  );

  // When the avatar bust is on screen we shrink the pill (~75%) and dim it
  // to 0.85 so the host stays the focal element.
  const effectiveFontSize = compact ? Math.round(fontSize * 0.74) : fontSize;
  const effectivePadding = compact ? "10px 22px" : "14px 32px";
  const effectiveOpacity = compact ? 0.92 : 1;
  // Pin the pill to the very bottom of the canvas when the avatar is on
  // screen — sits on the bust's chest area, not floating above the head.
  // Default (non-compact) keeps the legacy 240px bottom for older demos.
  const effectiveBottom = compact ? 60 : bottom;

  // Split-seam mode: the current word's scene is a horizontal 50/50 split,
  // so center the pill on the seam (y = seamY) instead of bottom-anchoring.
  const rideSeam = Boolean(current.splitSeam);

  const containerStyle: React.CSSProperties = rideSeam
    ? {
        position: "absolute",
        top: seamY,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: effectiveOpacity,
        transform: "translateY(-50%)",
      }
    : {
        position: "absolute",
        bottom: effectiveBottom,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: effectiveOpacity,
      };

  // Phase C (locked 2026-05-14): the pill is a TRANSLUCENT DARK SCRIM —
  // not opaque (Phase A's slab) and not fully transparent (Phase B's
  // experiment). A soft rgba(0,0,0,0.5) backdrop with strongly rounded
  // corners hugs the word so it stays legible over any underlying video
  // without reading as a UI element. Mirrors the reference reels (cf.
  // training data exp1/exp4).
  const wordColor = isAccent ? accentColor : textColor;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={containerStyle}>
        <div
          style={{
            fontFamily,
            fontSize: effectiveFontSize,
            fontWeight: 900,
            color: wordColor,
            background: "rgba(0, 0, 0, 0.5)",
            padding: effectivePadding,
            // Pill-shaped: half the line height makes the corners fully
            // rounded so the scrim hugs the word instead of squaring off.
            borderRadius: 9999,
            letterSpacing: -1.5,
            transform: `scale(${0.7 + reveal * 0.3})`,
            whiteSpace: "nowrap",
            textTransform: "lowercase",
          }}
        >
          {cleaned}
        </div>
      </div>
    </AbsoluteFill>
  );
};
