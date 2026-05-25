import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import { resolveSrc } from "./_mediaHelpers";

const { fontFamily } = loadFont();

/**
 * One stop on the paper walkthrough. Coordinates are in IMAGE coordinate
 * space (i.e. relative to the rendered tall paper PNG, NOT the viewport).
 * The renderer translates the image with `translateY(-scrollY)`. Phase B
 * removed the per-stop bbox highlight overlay — the global PillCaption
 * shows the active word and the scroll motion already directs the eye.
 */
export type WalkthroughStop = {
  /** Y position in IMAGE coords that should land at ~upper-third of viewport */
  scrollY: number;
  /** What the voice is saying at this stop — surfaced by the global subtitle. */
  caption: string;
  /** How long to hold at this stop, in seconds */
  dwell_sec: number;
};

type Props = {
  imageSrc: string;
  stops: WalkthroughStop[];
  /** Source label (e.g. "arXiv 2605.00833"), shown top-right */
  source?: string;
  accentColor?: string;
  /** Frames spent transitioning between two consecutive stops. Default 24 */
  transitionFrames?: number;
};

/**
 * Where each stop's `scrollY` row lands inside the visible canvas. Setting
 * this to 280 means the highlight sits ~25% from the top of the frame —
 * comfortable reading distance, away from the very edge, and well clear of
 * the avatar bust occupying the bottom ~760px.
 */
const TARGET_VIEWPORT_Y = 280;

const easeInOutCubic = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/**
 * Paper walkthrough — scroll-and-hold sequence over a tall PDF render.
 *
 * For each stop:
 *   1. Smoothly scroll from the previous stop's scrollY to this stop's
 *      scrollY over `transitionFrames` frames (eased).
 *   2. Hold at scrollY for `dwell_sec * fps` frames.
 *   3. While holding, animate a yellow highlight box behind the relevant
 *      text (text-selection style) and reveal the caption word-by-word at
 *      the bottom of the frame.
 *
 * Total scene duration is computed as:
 *     sum(dwell_sec * fps) + (stops.length - 1) * transitionFrames
 *
 * The renderer is responsible for setting `durationInFrames` to this value.
 */
export const PaperWalkthroughScene: React.FC<Props> = ({
  imageSrc,
  stops,
  source,
  accentColor = "#FFE066",
  transitionFrames = 24,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Compute the per-stop frame ranges. Each stop has [enter, hold_start, hold_end].
  type Range = {
    enterStart: number; // frame at which we BEGIN scrolling toward this stop
    holdStart: number;  // frame at which we ARRIVE at this stop
    holdEnd: number;    // frame at which we LEAVE this stop
  };
  const ranges: Range[] = [];
  let cursor = 0;
  for (let i = 0; i < stops.length; i++) {
    const isFirst = i === 0;
    const enterStart = cursor;
    const holdStart = isFirst ? cursor : cursor + transitionFrames;
    const holdEnd = holdStart + Math.max(1, Math.round(stops[i].dwell_sec * fps));
    ranges.push({ enterStart, holdStart, holdEnd });
    cursor = holdEnd;
  }

  // ── Determine current stop and scrollY ──────────────────────────────────
  let activeIdx = 0;
  let scrollY = stops[0].scrollY;

  for (let i = 0; i < stops.length; i++) {
    const r = ranges[i];
    if (frame < r.holdStart) {
      // Transitioning INTO stop i from stop i-1
      if (i === 0) {
        scrollY = stops[0].scrollY;
        activeIdx = 0;
      } else {
        const prev = stops[i - 1];
        const t = (frame - r.enterStart) / Math.max(1, r.holdStart - r.enterStart);
        const eased = easeInOutCubic(Math.max(0, Math.min(1, t)));
        scrollY = prev.scrollY + (stops[i].scrollY - prev.scrollY) * eased;
        // During transition we still consider the PREVIOUS stop as "active"
        // for caption purposes — the new caption fades in once we arrive.
        activeIdx = i - 1;
      }
      break;
    } else if (frame <= r.holdEnd) {
      scrollY = stops[i].scrollY;
      activeIdx = i;
      break;
    }
    // else: past this stop, continue
    if (i === stops.length - 1) {
      scrollY = stops[i].scrollY;
      activeIdx = i;
    }
  }

  // activeIdx is intentionally tracked for future per-stop annotations
  // even though Phase B removed the bbox highlight overlay.
  void activeIdx;

  // Soft entry fade for the whole scene
  const sceneEntry = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });
  const sceneExit = interpolate(
    frame,
    [durationInFrames - 10, durationInFrames],
    [1, 0.85],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0a0a", overflow: "hidden" }}>
      {/* Solid paper backdrop (was a radial gradient; flat per no-gradient rule). */}

      {/* The scrolling paper layer (image + highlight tracks together).
          We bias the scrolled row up by TARGET_VIEWPORT_Y so the active
          highlight lands in the upper-third of the visible canvas instead
          of at y=0 — that puts it visually CENTERED in the unobscured area
          above the avatar bust (which occupies the lower ~760px). */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          width: 1080,
          transform: `translateX(-50%) translateY(${TARGET_VIEWPORT_Y - scrollY}px)`,
          willChange: "transform",
          opacity: sceneEntry * sceneExit,
        }}
      >
        <Img
          src={resolveSrc(imageSrc)}
          style={{
            width: 1080,
            height: "auto",
            display: "block",
          }}
        />

        {/* Phase B: the per-stop yellow highlight box and arrow cursor
            were retired. The bbox coords were hallucinated by the LLM
            (which never saw the paper render) and landed all over the
            place. The global PillCaption already shows the current
            word, and the scroll motion already points the viewer at
            the relevant section, so we don't need extra emphasis. */}
      </div>

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
            background: "rgba(0,0,0,0.7)",
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
