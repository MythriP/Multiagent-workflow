// FloatingWindowScene — pattern 3.
//
// A floating "card" containing an image, video, map, or UI screenshot,
// centered on a dark dot-grid background. Single keyword subtitle under
// the window. Reads as a hover preview: the content sits on top of
// nothing, no other UI competing.

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
import { aspectRatioToCss, isVideoSrc, resolveSrc } from "./_mediaHelpers";
import { useSnapPauseSnap } from "../animations/useSnapPauseSnap";

const { fontFamily } = loadFont();

const CANVAS_W = 1080;
const CANVAS_H = 1920;

type Props = {
  windowSrc: string;
  /** Phase B: keyword pill retired. Prop accepted for back-compat;
   *  intentionally unused. */
  keyword?: string;
  windowAspect: "16:9" | "4:3" | "1:1" | "9:16";
  sourceLabel?: string;
  videoStartSec?: number;
  accentColor: string;
  vibe: VibeProfile;
};

export const FloatingWindowScene: React.FC<Props> = ({
  windowSrc,
  windowAspect,
  sourceLabel,
  videoStartSec,
  accentColor,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cfg = springConfigFor(vibe.motion_intensity);
  const snap = useSnapPauseSnap();

  const entry = spring({ frame, fps, config: cfg });
  const scale = interpolate(entry, [0, 1], [0.92, 1]);
  const opacity = interpolate(entry, [0, 1], [0, 1]);
  const lift = interpolate(entry, [0, 1], [40, 0]);

  // Phase C composition-relative anchoring:
  //
  // The window is sized to fill the writable area between the canvas
  // quiet zones (top 120 / bottom 220 reserved for source chip + global
  // subtitle), then centered within it. We scale the window so it fits
  // the writable area in BOTH dimensions while preserving the requested
  // aspect ratio — no implicit pinning to the bottom of the canvas.
  const QUIET_TOP = 120;
  const QUIET_BOTTOM = 220;
  const SAFE_PAD_X = 80;

  const writableW = CANVAS_W - 2 * SAFE_PAD_X;
  const writableH = CANVAS_H - QUIET_TOP - QUIET_BOTTOM;

  const [aw, ah] = windowAspect.split(":").map(Number);
  const aspect = aw / ah;
  // Fit-to-area scaling: pick the smaller of width-driven and
  // height-driven sizes so the window never escapes the writable box.
  let winW = writableW;
  let winH = Math.round(winW / aspect);
  if (winH > writableH) {
    winH = writableH;
    winW = Math.round(winH * aspect);
  }

  const winTop = QUIET_TOP + Math.round((writableH - winH) / 2);

  const resolvedSrc = resolveSrc(windowSrc);
  const videoStart = videoStartSec
    ? Math.round(videoStartSec * fps)
    : undefined;

  return (
    <AbsoluteFill style={{ opacity: snap.exitReveal }}>
      <VibeBackdrop vibe={vibe} surface="primary" dotGrid />

      <div
        style={{
          position: "absolute",
          left: (CANVAS_W - winW) / 2,
          top: winTop,
          width: winW,
          height: winH,
          opacity,
          transform: `translateY(${lift}px) scale(${scale})`,
          borderRadius: 22,
          overflow: "hidden",
          backgroundColor: vibe.color_palette.secondary_bg,
          border: `1px solid ${accentColor}33`,
          aspectRatio: aspectRatioToCss(windowAspect),
        }}
      >
        {isVideoSrc(windowSrc) ? (
          <OffthreadVideo
            src={resolvedSrc}
            muted
            startFrom={videoStart}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
          />
        ) : (
          <Img
            src={resolvedSrc}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
          />
        )}

        {sourceLabel ? (
          <div
            style={{
              position: "absolute",
              top: 16,
              left: 16,
              fontFamily,
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: 1,
              color: "#fff",
              backgroundColor: "rgba(0,0,0,0.7)",
              padding: "5px 10px",
              borderRadius: 4,
            }}
          >
            {sourceLabel}
          </div>
        ) : null}
      </div>

      {/* Phase B: per-scene keyword retired in favor of the global
          PillCaption. `keyword` prop accepted for back-compat; not
          rendered. */}
    </AbsoluteFill>
  );
};
