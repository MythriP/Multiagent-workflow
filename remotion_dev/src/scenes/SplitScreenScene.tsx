// SplitScreenScene — pattern 1.
//
// Top/bottom split (vertical/left-right splits are forbidden in Phase B
// — Python coerces any "vertical" emission to "horizontal" before the
// scene reaches this component). Each pane enters from an OPPOSING
// direction and locks into place. Combinations:
//   text + image, text + video, image + image, video + video, image + video.
// Never text + text.
//
// Motion: each pane springs in from its `slide_from` direction, then holds
// completely still. No drift, no zoom, no Ken Burns. The "locking into
// place" feeling is the entire point of the animation.
//
// Seam math (Phase B): the canvas seam sits at exactly y=960 (canvas
// midpoint). Pane A occupies y=0..960, pane B occupies y=960..1920. The
// global PillCaption rides the seam at y=960 for split-screen scenes, so
// keeping panes flush with the canvas midpoint is the entire reason the
// math is laid out this way.

import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { VibeProfile } from "../DynamicReel";
import { VibeBackdrop, springConfigFor } from "../components/VibeBackdrop";
import { isVideoSrc, resolveSrc } from "./_mediaHelpers";
import { useSnapPauseSnap } from "../animations/useSnapPauseSnap";
import { MixedTypeText } from "../components/MixedTypeText";

const { fontFamily } = loadFont();

const CANVAS_W = 1080;
const CANVAS_H = 1920;
// Each pane is exactly half the canvas. The seam lives at y = CANVAS_H/2.
const PANE_H = CANVAS_H / 2;
const SEAM_Y = CANVAS_H / 2;

type Pane = {
  kind: "text" | "media";
  text?: string | null;
  src?: string | null;
  source_label?: string | null;
  slide_from: "top" | "bottom" | "left" | "right";
  accent_italic_words?: string[] | null;
};

type Props = {
  orientation: "horizontal" | "vertical";
  paneA: Pane;
  paneB: Pane;
  /** Phase B retired the scene-level keyword pill. Prop is kept on the
   *  type for back-compat with older callers; component ignores it. */
  keyword?: string;
  accentColor: string;
  vibe: VibeProfile;
};

const PaneContent: React.FC<{
  pane: Pane;
  width: number;
  height: number;
  vibe: VibeProfile;
  accentColor: string;
}> = ({ pane, width, height, vibe, accentColor }) => {
  if (pane.kind === "text") {
    const text = pane.text ?? "";
    const italicWords = pane.accent_italic_words ?? [];
    return (
      <div
        style={{
          width,
          height,
          backgroundColor: vibe.color_palette.secondary_bg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 70,
          boxSizing: "border-box",
          position: "relative",
        }}
      >
        <MixedTypeText
          text={text}
          italicWords={italicWords}
          size={72}
          color={vibe.color_palette.text_primary}
          italicColor={accentColor}
          letterSpacing={-1.5}
          lineHeight={1.16}
          align="left"
          uppercaseSans={false}
          style={{ maxWidth: width - 100 }}
        />
        {pane.source_label ? (
          <div
            style={{
              position: "absolute",
              top: 40,
              left: 40,
              fontFamily,
              color: accentColor,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: 1.5,
              textTransform: "uppercase",
              padding: "6px 14px",
              borderRadius: 4,
              border: `2px solid ${accentColor}`,
            }}
          >
            {pane.source_label}
          </div>
        ) : null}
      </div>
    );
  }

  const src = pane.src ?? "";
  if (!src) {
    return (
      <div
        style={{
          width,
          height,
          backgroundColor: vibe.color_palette.secondary_bg,
        }}
      />
    );
  }
  const resolved = resolveSrc(src);
  return (
    <div
      style={{
        width,
        height,
        overflow: "hidden",
        backgroundColor: "#000",
        position: "relative",
      }}
    >
      {isVideoSrc(src) ? (
        <OffthreadVideo
          src={resolved}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <Img
          src={resolved}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}
      {pane.source_label ? (
        <div
          style={{
            position: "absolute",
            top: 24,
            left: 24,
            fontFamily,
            color: "#fff",
            backgroundColor: "rgba(0,0,0,0.7)",
            fontSize: 20,
            fontWeight: 600,
            letterSpacing: 0.8,
            padding: "6px 12px",
            borderRadius: 4,
          }}
        >
          {pane.source_label}
        </div>
      ) : null}
    </div>
  );
};

export const SplitScreenScene: React.FC<Props> = ({
  paneA,
  paneB,
  accentColor,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cfg = springConfigFor(vibe.motion_intensity);
  // Scene-level snap-pause-snap. `exitReveal` lets the scene snap-cut at
  // its tail instead of hard-cutting mid-content.
  const snap = useSnapPauseSnap();

  // Spring 0 -> 1 for each pane. Both start at frame 0 so they meet at
  // the seam simultaneously.
  const progressA = spring({ frame, fps, config: cfg });
  const progressB = spring({ frame, fps, config: cfg });

  // For horizontal splits (the only flavor in Phase B), valid slide
  // directions are "top" / "bottom". Anything else gets coerced to a
  // sane default so the panes still land in place.
  const slideY = (
    direction: Pane["slide_from"],
    progress: number,
    paneIsTop: boolean
  ): number => {
    const eased = interpolate(progress, [0, 1], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    if (direction === "top") return -PANE_H * eased;
    if (direction === "bottom") return PANE_H * eased;
    // Coerce legacy left/right to a deterministic top/bottom pair.
    return (paneIsTop ? -PANE_H : PANE_H) * eased;
  };

  const offsetA = slideY(paneA.slide_from, progressA, true);
  const offsetB = slideY(paneB.slide_from, progressB, false);

  return (
    <AbsoluteFill style={{ opacity: snap.exitReveal }}>
      <VibeBackdrop vibe={vibe} surface="primary" />

      {/* Top pane (y=0..960) */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: CANVAS_W,
          height: PANE_H,
          transform: `translateY(${offsetA}px)`,
        }}
      >
        <PaneContent
          pane={paneA}
          width={CANVAS_W}
          height={PANE_H}
          vibe={vibe}
          accentColor={accentColor}
        />
      </div>

      {/* Bottom pane (y=960..1920) */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: SEAM_Y,
          width: CANVAS_W,
          height: PANE_H,
          transform: `translateY(${offsetB}px)`,
        }}
      >
        <PaneContent
          pane={paneB}
          width={CANVAS_W}
          height={PANE_H}
          vibe={vibe}
          accentColor={accentColor}
        />
      </div>

      {/* Crisp seam exactly at y=960. Matches the PillCaption seam anchor
          so the subtitle pill straddles the divider precisely. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: SEAM_Y - 2,
          height: 4,
          backgroundColor: vibe.color_palette.primary_bg,
        }}
      />
    </AbsoluteFill>
  );
};
