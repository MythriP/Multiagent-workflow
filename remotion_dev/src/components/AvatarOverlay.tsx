import {
  AbsoluteFill,
  Img,
  staticFile,
  Video,
} from "remotion";

/**
 * Reserved bottom region for the talking-head bust. Scene components should
 * keep critical content (key text, paper figures, charts) above
 * AVATAR_SAFE_BOTTOM in the 1080×1920 canvas so the avatar doesn't cover them.
 */
export const AVATAR_BUST_HEIGHT = 880; // visible vertical extent of the bust
export const AVATAR_BUST_TOP = 1920 - AVATAR_BUST_HEIGHT; // 1040
export const AVATAR_SAFE_BOTTOM = AVATAR_BUST_TOP - 40;

type Props = {
  /** Image fallback. Cutout PNG with transparent background (rembg-processed). */
  imageSrc?: string;
  /** Optional fal.ai/VEED lip-sync video source. When present, replaces the still. */
  videoSrc?: string;
  /**
   * Per-frame opacity (0–1). DynamicReel computes a smoothed timeline based
   * on which scenes are "narrator-on-camera" vs "full-canvas". Default 1.
   */
  opacity?: number;
};

/**
 * Talking-head avatar — a transparent-background bust of the speaker rooted
 * to the bottom-center of the frame. Renders the FULL cutout (head +
 * shoulders + chest) and fades a soft black gradient up from the bottom
 * so:
 *   • The bust feels grounded — not "floating".
 *   • The subtitle pill at the very bottom has a dark backdrop to sit on.
 *   • Image scenes that have busy / light bottom edges don't fight the
 *     bust's silhouette.
 *
 * Source asset is `avatar/headshot.png`. The headshot's natural aspect
 * drives the rendered bust dimensions — if you swap in a taller source,
 * the bust gets taller automatically.
 */
export const AvatarOverlay: React.FC<Props> = ({
  imageSrc = "avatar/headshot.png",
  videoSrc,
  opacity = 1,
}) => {
  // No breathing wobble — kills the bobbing-on-still-PNG artifact. When we
  // swap in a real lip-sync video, micro-motion comes from that asset.
  const breathe = 1;

  // Sliding the bust down and dimming when the parent fades it out.
  const slideY = (1 - opacity) * 80;

  if (opacity < 0.02) return null;

  // Render box. We render the cutout at full canvas width and let
  // objectFit: contain show the entire image — head + shoulders + chest.
  // No bottom-crop trick anymore (used to clip 140px off the bottom which
  // hid the body even when the source had it).
  const width = 1080;
  const height = AVATAR_BUST_HEIGHT;
  const left = 0;
  const top = AVATAR_BUST_TOP;

  // Black-fade gradient. Starts higher than the bust top so it transitions
  // smoothly from the scene above into the bust area. Base opacity rides
  // with the avatar's own opacity so it fades together.
  const fadeTop = AVATAR_BUST_TOP - 120; // start fading 120px above bust
  const fadeHeight = 1920 - fadeTop;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Soft black gradient grounding the bust + giving the subtitle
          pill a clean backdrop. Fully opaque at the very bottom (where
          the pill sits) and transparent at the top of the fade region. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: fadeTop,
          height: fadeHeight,
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,0.55) 35%, rgba(0,0,0,0.88) 75%, rgba(0,0,0,0.95) 100%)",
          opacity,
        }}
      />

      {/* The bust itself */}
      <div
        style={{
          position: "absolute",
          left,
          top,
          width,
          height,
          opacity,
          transform: `translateY(${slideY}px) scale(${breathe})`,
          transformOrigin: "50% 100%",
          // Soft drop shadow so the bust reads as foreground over light
          // image scenes without a hard outline.
          filter: "drop-shadow(0 24px 36px rgba(0,0,0,0.55))",
        }}
      >
        {videoSrc ? (
          <Video
            src={staticFile(videoSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              objectPosition: "center bottom",
            }}
          />
        ) : (
          <Img
            src={staticFile(imageSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              objectPosition: "center bottom",
            }}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
