import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { VibeProfile } from "../DynamicReel";

const { fontFamily } = loadFont();

// Canvas is 1080×1920 (9:16). The hook splits this exactly in half — top
// pane is a typography card on pure black, bottom pane is the avatar's real
// environment photo. Top pane y=0..960, bottom pane y=960..1920.
//
// Global rules respected here:
//   • No glow: no textShadow, no boxShadow.
//   • No gradient: top pane is solid #000, not vibe primary_bg.
//   • Bottom-pane photo is STATIC — no translateY entry motion.
const CANVAS_H = 1920;
const SPLIT_Y = CANVAS_H / 2;

type Props = {
  hook: string;
  subtitle: string;
  accentColor: string;
  /** Optional ambient background — kept in signature for back-compat with
   *  callers, but the 50/50 layout intentionally ignores it. */
  bgMediaSrc?: string;
  /** Vibe profile from vibe_planner. Used for text color only. */
  vibe?: VibeProfile | null;
  /** Phase C lipsync (Option B). When present, the bottom pane plays
   *  this mp4 (avatar talking) instead of the still avatar-source.png. */
  lipsyncClipSrc?: string;
  lipsyncClipStartSec?: number;
};

export const HookCard: React.FC<Props> = ({
  hook,
  subtitle,
  accentColor,
  vibe,
  lipsyncClipSrc,
  lipsyncClipStartSec,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleScale = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 130, mass: 0.6 },
  });
  const titleOpacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subOpacity = interpolate(frame, [10, 22], [0, 1], {
    extrapolateRight: "clamp",
  });
  const subY = interpolate(frame, [10, 22], [40, 0], {
    extrapolateRight: "clamp",
  });

  const textPrimary = vibe?.color_palette.text_primary ?? "#ffffff";

  return (
    <AbsoluteFill style={{ background: "#000000" }}>
      {/* ── Top pane: typography card on pure black (y=0..960) ───────────── */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: "100%",
          height: SPLIT_Y,
          background: "#000000",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px",
          opacity: titleOpacity,
        }}
      >
        <div
          style={{
            fontFamily,
            color: textPrimary,
            fontSize: 118,
            fontWeight: 900,
            textAlign: "center",
            lineHeight: 1.02,
            letterSpacing: -3,
            transform: `scale(${0.92 + titleScale * 0.08})`,
          }}
        >
          {hook}
        </div>
        <div
          style={{
            fontFamily,
            color: accentColor,
            fontSize: 64,
            fontWeight: 800,
            marginTop: 28,
            letterSpacing: -1.5,
            opacity: subOpacity,
            transform: `translateY(${subY}px)`,
            textTransform: "uppercase",
            textAlign: "center",
          }}
        >
          {subtitle}
        </div>
        <div
          style={{
            width: 160 + titleScale * 180,
            height: 6,
            background: accentColor,
            marginTop: 40,
            borderRadius: 3,
            opacity: subOpacity,
          }}
        />
      </div>

      {/* ── Bottom pane: avatar lipsync video (Phase C) or still photo
              fallback (y=960..1920). When lipsyncClipSrc is provided
              the pane plays the OmniHuman talking-head clip generated
              from avatar-source.png; otherwise it shows the still PNG. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: SPLIT_Y,
          width: "100%",
          height: CANVAS_H - SPLIT_Y,
          overflow: "hidden",
          background: "#000000",
        }}
      >
        {lipsyncClipSrc ? (
          <OffthreadVideo
            src={staticFile(lipsyncClipSrc)}
            muted
            startFrom={
              lipsyncClipStartSec
                ? Math.round(lipsyncClipStartSec * fps)
                : undefined
            }
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center 35%",
            }}
          />
        ) : (
          <Img
            src={staticFile("avatar/avatar-source.png")}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center 35%",
            }}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
