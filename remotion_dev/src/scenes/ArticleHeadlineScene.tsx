// ArticleHeadlineScene — pattern 5.
//
// An article headline / screenshot sits in the upper half with a colored
// selection box drawn around a key phrase (like a browser highlight). A
// relevant emotional / contextual image sits below. A word callout pops
// over the emotional image when the narration hits its keyword (centered
// at duration_sec / 2).

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

type Bbox = { x: number; y: number; w: number; h: number };

type Props = {
  articleSrc: string;
  highlightPhrase: string;
  highlightBbox?: Bbox;
  emotionalSrc?: string;
  wordCallout: string;
  sourceLabel?: string;
  accentColor: string;
  vibe: VibeProfile;
};

export const ArticleHeadlineScene: React.FC<Props> = ({
  articleSrc,
  highlightPhrase,
  highlightBbox,
  emotionalSrc,
  wordCallout,
  sourceLabel,
  accentColor,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const cfg = springConfigFor(vibe.motion_intensity);
  const snap = useSnapPauseSnap();

  const entry = spring({ frame, fps, config: cfg });
  const articleY = interpolate(entry, [0, 1], [-60, 0]);
  const emotionalY = interpolate(entry, [0, 1], [80, 0]);
  const articleOpacity = interpolate(entry, [0, 1], [0, 1]);

  // Highlight box appears after the article lands.
  const highlightProgress = spring({
    frame: frame - Math.round(fps * 0.5),
    fps,
    config: cfg,
  });
  const highlightWidthFactor = interpolate(highlightProgress, [0, 1], [0, 1]);

  // Word callout pops at duration/2.
  const calloutStart = Math.round(durationInFrames * 0.45);
  const calloutSpring = spring({
    frame: frame - calloutStart,
    fps,
    config: cfg,
  });
  const calloutScale = interpolate(calloutSpring, [0, 1], [0.7, 1]);
  const calloutOpacity = interpolate(calloutSpring, [0, 0.4, 1], [0, 1, 1], {
    extrapolateRight: "clamp",
  });

  // Phase C composition-relative anchoring:
  //
  // Article + emotional image form a single block centered between the
  // canvas quiet zones. With both present the block uses two equal-ish
  // panes; with only the article it is centered alone. Top/bottom
  // ~120/220 px stay clear so source chip + global subtitle have room.
  const QUIET_TOP = 120;
  const QUIET_BOTTOM = 220;
  const PANE_GAP = 60;

  const writableH = CANVAS_H - QUIET_TOP - QUIET_BOTTOM;
  const hasEmotional = !!emotionalSrc;
  const paneH = hasEmotional
    ? Math.floor((writableH - PANE_GAP) / 2)
    : writableH;
  const articleH = paneH;
  const articleTop = QUIET_TOP;
  const emotionalH = paneH;
  const emotionalTop = articleTop + articleH + PANE_GAP;

  const bbox = highlightBbox ?? {
    // Centered placeholder near the top of the article image
    x: 0.08,
    y: 0.12,
    w: 0.84,
    h: 0.1,
  };

  return (
    <AbsoluteFill style={{ opacity: snap.exitReveal }}>
      <VibeBackdrop vibe={vibe} surface="primary" />

      {/* Article image with highlight box */}
      <div
        style={{
          position: "absolute",
          left: 40,
          right: 40,
          top: articleTop,
          height: articleH,
          opacity: articleOpacity,
          transform: `translateY(${articleY}px)`,
          borderRadius: 14,
          overflow: "hidden",
          backgroundColor: "#fff",
        }}
      >
        {isVideoSrc(articleSrc) ? (
          <OffthreadVideo
            src={resolveSrc(articleSrc)}
            muted
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }}
          />
        ) : (
          <Img
            src={resolveSrc(articleSrc)}
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }}
          />
        )}
        {/* Colored selection box like a browser highlight */}
        {highlightPhrase ? (
          <div
            style={{
              position: "absolute",
              left: `${bbox.x * 100}%`,
              top: `${bbox.y * 100}%`,
              width: `${bbox.w * highlightWidthFactor * 100}%`,
              height: `${bbox.h * 100}%`,
              backgroundColor: `${accentColor}66`,
              border: `2px solid ${accentColor}`,
              borderRadius: 4,
              pointerEvents: "none",
            }}
          />
        ) : null}

        {sourceLabel ? (
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              fontFamily,
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: 1,
              color: "#fff",
              backgroundColor: "rgba(0,0,0,0.8)",
              padding: "4px 10px",
              borderRadius: 4,
            }}
          >
            {sourceLabel}
          </div>
        ) : null}
      </div>

      {/* Emotional image below */}
      {emotionalSrc ? (
        <div
          style={{
            position: "absolute",
            left: 40,
            right: 40,
            top: emotionalTop,
            height: emotionalH,
            opacity: articleOpacity,
            transform: `translateY(${emotionalY}px)`,
            borderRadius: 14,
            overflow: "hidden",
            backgroundColor: "#000",
          }}
        >
          {isVideoSrc(emotionalSrc) ? (
            <OffthreadVideo
              src={resolveSrc(emotionalSrc)}
              muted
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <Img
              src={resolveSrc(emotionalSrc)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          )}
          {/* Word callout */}
          {wordCallout ? (
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: "50%",
                display: "flex",
                justifyContent: "center",
                transform: `translateY(-50%) scale(${calloutScale})`,
                opacity: calloutOpacity,
              }}
            >
              <div
                style={{
                  fontFamily,
                  color: vibe.color_palette.primary_bg,
                  backgroundColor: accentColor,
                  fontSize: 84,
                  fontWeight: 900,
                  padding: "18px 38px",
                  borderRadius: 16,
                  letterSpacing: -2,
                  textTransform: "uppercase",
                }}
              >
                {wordCallout}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
