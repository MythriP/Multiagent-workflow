import { spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Phase tag returned by useSnapPauseSnap.
 *   "in"    → the ~5-frame snap-in window at the start of the scene.
 *   "dwell" → the held middle. Use the `progress` field (0..1) to drive
 *             subtle ambient motion (zoom drift, parallax, etc.).
 *   "out"   → the ~5-frame snap-out window at the end of the scene.
 */
export type SnapPhase = "in" | "dwell" | "out";

export type SnapPauseSnapResult = {
  phase: SnapPhase;
  /** 0..1 progress within the CURRENT phase only. */
  progress: number;
  /** Convenience headline value: 0 → 1 hard during "in", 1 during "dwell",
   *  1 → 0 hard during "out". Useful for opacity / mask / scale anchors. */
  reveal: number;
  /** Just the snap-in component (0 → 1, then held at 1). Scenes that
   *  already do their own custom entry motion can ignore this and use only
   *  `exitReveal` to bolt on the snap-out. */
  entryReveal: number;
  /** Just the snap-out component (1 during dwell, then 1 → 0 hard at the
   *  end). Multiply into your root opacity to get the hard exit for free. */
  exitReveal: number;
};

type Args = {
  /** Frames per second. If omitted, pulled from useVideoConfig(). */
  fps?: number;
  /** Total duration of the scene/segment in frames. If omitted, falls back
   *  to useVideoConfig().durationInFrames (which inside a <Sequence>
   *  returns the local sequence's duration). */
  durationInFrames?: number;
  /** Length of the snap-in window in frames. Default 5 (high-stiffness). */
  snapInFrames?: number;
  /** Length of the snap-out window in frames. Default 5. */
  snapOutFrames?: number;
  /** Optional override: use this frame instead of useCurrentFrame(). */
  frame?: number;
};

const SNAP_SPRING = { damping: 12, stiffness: 320, mass: 0.45 };

/**
 * Implements the global "sudden → slow → sudden" motion law (locked
 * 2026-05-13). All scene entry/exit animations should be driven by this
 * hook so the reel reads as cinematic snaps with a calm dwell between them
 * instead of constant gentle drift.
 *
 * Phase 1 (in, ~5 frames):  high-stiffness spring from 0 → 1.
 * Phase 2 (dwell):           held flat at 1; emit `progress` for ambient.
 * Phase 3 (out, ~5 frames):  mirror of phase 1, 1 → 0, hard cut.
 *
 * The `reveal` value is the simple all-in-one drive you can multiply into
 * `opacity` or `scale` to get the right snap behavior for free. For
 * ambient dwell motion (slow zoom, parallax pan, highlight pulse), read
 * `phase === "dwell"` and `progress` (0..1) and drive your own curve.
 */
export const useSnapPauseSnap = ({
  fps,
  durationInFrames,
  snapInFrames = 5,
  snapOutFrames = 5,
  frame,
}: Args = {}): SnapPauseSnapResult => {
  const liveFrame = useCurrentFrame();
  const config = useVideoConfig();
  const f = typeof frame === "number" ? frame : liveFrame;
  const effFps = fps ?? config.fps;
  const effDuration =
    typeof durationInFrames === "number"
      ? durationInFrames
      : config.durationInFrames;

  const total = Math.max(1, Math.round(effDuration));
  const inEnd = Math.min(total, snapInFrames);
  const outStart = Math.max(inEnd, total - snapOutFrames);

  if (f < inEnd) {
    const phaseProgress = inEnd > 0 ? f / inEnd : 1;
    const reveal = spring({ frame: f, fps: effFps, config: SNAP_SPRING });
    return {
      phase: "in",
      progress: phaseProgress,
      reveal,
      entryReveal: reveal,
      exitReveal: 1,
    };
  }

  if (f < outStart) {
    const dwellSpan = Math.max(1, outStart - inEnd);
    const phaseProgress = (f - inEnd) / dwellSpan;
    return {
      phase: "dwell",
      progress: phaseProgress,
      reveal: 1,
      entryReveal: 1,
      exitReveal: 1,
    };
  }

  const outSpan = Math.max(1, total - outStart);
  const localOut = Math.min(outSpan, f - outStart);
  const fallReveal =
    1 -
    spring({
      frame: localOut,
      fps: effFps,
      config: SNAP_SPRING,
    });
  const phaseProgress = localOut / outSpan;
  return {
    phase: "out",
    progress: phaseProgress,
    reveal: fallReveal,
    entryReveal: 1,
    exitReveal: fallReveal,
  };
};
