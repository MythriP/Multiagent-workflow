// PipelineHighlightScene — pattern 2 (Phase B rebuild).
//
// Show a full diagram / pipeline / architecture screenshot. The legacy
// bbox highlight system was retired: the LLM never sees the image, so it
// hallucinated coordinates and the rectangles landed in empty space.
//
// New design:
//   • Diagram fills the safe area (with objectFit: contain).
//   • Top strip optionally carries a bold editorial top_annotation.
//   • Bottom strip optionally carries a bold editorial bottom_annotation.
//   • Source chip stays in the top-right corner.
//   • If animated_src is provided (a Veo clip), it plays instead of the
//     static diagram.
//
// Motion: the diagram snap-fades in once via useSnapPauseSnap. Annotations
// drift in 5 frames behind the diagram via a small opposing-direction
// slide. No bbox glow, no halo.

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

// Phase C anchoring rule: text labels hug the visual, not the canvas.
// We render diagram + top_annotation + bottom_annotation as a single
// vertical block, centered in the canvas. The block is bounded by the
// "quiet zones" — top 120px / bottom 220px — so the source chip and
// the global PillCaption have room without overlapping the body.
const CANVAS_W = 1080;
const CANVAS_H = 1920;
const QUIET_TOP = 120;
const QUIET_BOTTOM = 220;
// Vertical gap between the diagram and an adjacent annotation.
const ANNOTATION_GAP = 36;

type Props = {
  diagramSrc: string;
  animatedSrc?: string;
  source?: string;
  topAnnotation?: string;
  bottomAnnotation?: string;
  accentColor: string;
  vibe: VibeProfile;
};

export const PipelineHighlightScene: React.FC<Props> = ({
  diagramSrc,
  animatedSrc,
  source,
  topAnnotation,
  bottomAnnotation,
  accentColor,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cfg = springConfigFor(vibe.motion_intensity);
  const snap = useSnapPauseSnap();

  // Diagram snaps in.
  const entry = spring({ frame, fps, config: cfg });
  const diagramOpacity = interpolate(entry, [0, 1], [0, 1]);
  const diagramScale = interpolate(entry, [0, 1], [0.96, 1]);

  // Annotations slide in from opposing directions, 5 frames behind.
  const annotEntry = spring({
    frame: frame - 5,
    fps,
    config: cfg,
  });
  const annotOpacity = interpolate(annotEntry, [0, 1], [0, 1]);
  const topAnnotY = interpolate(annotEntry, [0, 1], [-40, 0]);
  const bottomAnnotY = interpolate(annotEntry, [0, 1], [40, 0]);

  const showAnimated = !!animatedSrc;
  const hasTop = !!topAnnotation;
  const hasBottom = !!bottomAnnotation;

  // Composition-relative anchoring (Phase C):
  //
  // Compose annotations + diagram as a single vertical block, vertically
  // centered between the canvas quiet zones (top 120 / bottom 220). The
  // block grows or shrinks based on which annotations are present, so
  // labels always sit immediately above / below the diagram instead of
  // being pinned to the canvas edges. The diagram absorbs the freed
  // vertical space as the available block height grows.
  const blockMaxH = CANVAS_H - QUIET_TOP - QUIET_BOTTOM; // ≈ 1580
  // Reserve ~110px per annotation slot (single-line bold text + gap).
  const ANNOT_SLOT_H = 130;
  const reserved =
    (hasTop ? ANNOT_SLOT_H + ANNOTATION_GAP : 0) +
    (hasBottom ? ANNOT_SLOT_H + ANNOTATION_GAP : 0);
  const diagramH = blockMaxH - reserved;
  const diagramW = CANVAS_W - 80; // 40px padding either side

  return (
    <AbsoluteFill style={{ opacity: snap.exitReveal }}>
      <VibeBackdrop vibe={vibe} surface="primary" dotGrid />

      {/* Source chip top-right (lives in the top quiet zone). */}
      {source ? (
        <div
          style={{
            position: "absolute",
            top: 40,
            right: 40,
            fontFamily,
            fontSize: 20,
            fontWeight: 700,
            letterSpacing: 1.2,
            color: vibe.color_palette.text_primary,
            backgroundColor: vibe.color_palette.secondary_bg,
            padding: "6px 14px",
            borderRadius: 6,
            border: `1px solid ${accentColor}44`,
            zIndex: 2,
          }}
        >
          {source}
        </div>
      ) : null}

      {/* Composition block — annotations hug the diagram. The block is
          centered in the writable area between the two quiet zones. */}
      <div
        style={{
          position: "absolute",
          top: QUIET_TOP,
          bottom: QUIET_BOTTOM,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "0 40px",
        }}
      >
        {hasTop ? (
          <div
            style={{
              width: "100%",
              height: ANNOT_SLOT_H,
              marginBottom: ANNOTATION_GAP,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: annotOpacity,
              transform: `translateY(${topAnnotY}px)`,
            }}
          >
            <MixedTypeText
              text={topAnnotation as string}
              size={62}
              color={vibe.color_palette.text_primary}
              italicColor={accentColor}
              letterSpacing={-1.5}
              align="center"
              uppercaseSans
            />
          </div>
        ) : null}

        <div
          style={{
            width: diagramW,
            height: diagramH,
            opacity: diagramOpacity,
            transform: `scale(${diagramScale})`,
            backgroundColor: vibe.color_palette.secondary_bg,
            borderRadius: 18,
            overflow: "hidden",
          }}
        >
          {showAnimated && animatedSrc ? (
            <OffthreadVideo
              src={resolveSrc(animatedSrc)}
              muted
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          ) : isVideoSrc(diagramSrc) ? (
            <OffthreadVideo
              src={resolveSrc(diagramSrc)}
              muted
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          ) : (
            <Img
              src={resolveSrc(diagramSrc)}
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          )}
        </div>

        {hasBottom ? (
          <div
            style={{
              width: "100%",
              height: ANNOT_SLOT_H,
              marginTop: ANNOTATION_GAP,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: annotOpacity,
              transform: `translateY(${bottomAnnotY}px)`,
            }}
          >
            <MixedTypeText
              text={bottomAnnotation as string}
              size={56}
              color={vibe.color_palette.text_primary}
              italicColor={accentColor}
              letterSpacing={-1.4}
              align="center"
              uppercaseSans
            />
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
