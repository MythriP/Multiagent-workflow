// NumberedRevealScene — pattern 4.
//
// Colored background. A circle holding a number animates in from the left,
// followed by bold title text expanding to the right (circle -> label
// motion the user specifically asked for). An optional content window
// (image or video) appears below the row. A keyword subtitle sits at the
// bottom of the safe area.
//
// Used for "1, 2, 3" beats and numbered explainer points.

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

const { fontFamily } = loadFont();

const CANVAS_W = 1080;
const CANVAS_H = 1920;

type Props = {
  number: number;
  title: string;
  windowSrc?: string;
  /** Phase B: keyword pill retired. Prop accepted for back-compat;
   *  intentionally unused. */
  keyword?: string;
  videoStartSec?: number;
  accentColor: string;
  vibe: VibeProfile;
};

export const NumberedRevealScene: React.FC<Props> = ({
  number,
  title,
  windowSrc,
  videoStartSec,
  accentColor,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cfg = springConfigFor(vibe.motion_intensity);
  const snap = useSnapPauseSnap();

  // Circle pops in first.
  const circleStart = 0;
  const titleStart = Math.round(fps * 0.22); // 220ms behind the circle
  const windowStart = Math.round(fps * 0.5);

  const circleSpring = spring({ frame: frame - circleStart, fps, config: cfg });
  const circleScale = interpolate(circleSpring, [0, 1], [0, 1]);

  // Title expanding rectangle: width animates from 0 to the natural width,
  // then text fades in.
  const titleProgress = spring({ frame: frame - titleStart, fps, config: cfg });
  const titleWidthFactor = interpolate(titleProgress, [0, 1], [0, 1]);
  const titleTextOpacity = interpolate(titleProgress, [0.4, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const windowProgress = spring({ frame: frame - windowStart, fps, config: cfg });
  const windowOpacity = interpolate(windowProgress, [0, 1], [0, 1]);
  const windowY = interpolate(windowProgress, [0, 1], [60, 0]);

  // Phase C composition-relative anchoring:
  //
  // The numbered title row + content window form a single block centered
  // between the canvas quiet zones (top 120 / bottom 220). When no
  // window is present the row sits at center; when a window is present
  // the row hugs the top of the window with a small gap.
  const QUIET_TOP = 120;
  const QUIET_BOTTOM = 220;
  const ROW_GAP = 60;

  const circleSize = 180;
  const circleX = 80;
  const titleX = circleX + circleSize + 28;

  const winW = CANVAS_W - 160;
  const winH = Math.round((winW * 9) / 16);

  // Vertical centering math.
  const blockTotalH = windowSrc ? circleSize + ROW_GAP + winH : circleSize;
  const writableTop = QUIET_TOP;
  const writableH = CANVAS_H - QUIET_TOP - QUIET_BOTTOM;
  const blockTop = writableTop + Math.max(0, (writableH - blockTotalH) / 2);
  const rowY = blockTop;
  const winTop = rowY + circleSize + ROW_GAP;

  return (
    <AbsoluteFill style={{ opacity: snap.exitReveal }}>
      <VibeBackdrop vibe={vibe} surface="secondary" />

      {/* Numbered circle */}
      <div
        style={{
          position: "absolute",
          left: circleX,
          top: rowY,
          width: circleSize,
          height: circleSize,
          borderRadius: "50%",
          backgroundColor: accentColor,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transform: `scale(${circleScale})`,
        }}
      >
        <div
          style={{
            fontFamily,
            fontSize: 110,
            fontWeight: 900,
            color: vibe.color_palette.primary_bg,
            letterSpacing: -3,
          }}
        >
          {number}
        </div>
      </div>

      {/* Expanding title pill */}
      <div
        style={{
          position: "absolute",
          left: titleX,
          top: rowY + 36,
          height: circleSize - 72,
          width: (CANVAS_W - titleX - 80) * titleWidthFactor,
          backgroundColor: vibe.color_palette.primary_bg,
          borderRadius: 22,
          display: "flex",
          alignItems: "center",
          paddingLeft: 28,
          paddingRight: 28,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            fontFamily,
            fontSize: 56,
            fontWeight: 800,
            color: vibe.color_palette.text_primary,
            letterSpacing: -1.2,
            opacity: titleTextOpacity,
            whiteSpace: "nowrap",
          }}
        >
          {title}
        </div>
      </div>

      {/* Optional content window */}
      {windowSrc ? (
        <div
          style={{
            position: "absolute",
            left: (CANVAS_W - winW) / 2,
            top: winTop,
            width: winW,
            height: winH,
            opacity: windowOpacity,
            transform: `translateY(${windowY}px)`,
            borderRadius: 18,
            overflow: "hidden",
            backgroundColor: vibe.color_palette.primary_bg,
          }}
        >
          {/* objectFit: "contain" so the source's natural aspect is
              preserved — no center-crop. The container's vibe color acts
              as a letterbox for portrait or square sources. Phase B
              rule: nothing on screen is force-cropped to a fixed box
              unless it was generated to that aspect. */}
          {isVideoSrc(windowSrc) ? (
            <OffthreadVideo
              src={resolveSrc(windowSrc)}
              muted
              startFrom={
                videoStartSec ? Math.round(videoStartSec * fps) : undefined
              }
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
              }}
            />
          ) : (
            <Img
              src={resolveSrc(windowSrc)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
              }}
            />
          )}
        </div>
      ) : null}

      {/* The scene-level keyword pill was retired in Phase B (it
          double-stamped the global PillCaption). The `keyword` prop is
          still accepted for back-compat with older scripts; it's
          intentionally not rendered here. */}
    </AbsoluteFill>
  );
};
