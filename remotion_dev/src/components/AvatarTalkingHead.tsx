import {
  AbsoluteFill,
  Img,
  staticFile,
  useCurrentFrame,
  Video,
} from "remotion";

/**
 * Bottom-40% talking-head region. Designed to mimic the layout in the
 * training reels: the visual / screenshot lives in the top 60% of the
 * frame (canvas y < AVATAR_TOP), and the talking head fills the bottom
 * 40% of the frame edge-to-edge — no PiP circle, no LIVE badge, no
 * waveform widget. Just the person, like the example reel.
 *
 * Captions sit ON TOP of this region (around y=1520), the way they
 * appear over the speaker's chest in the training reels.
 *
 * Until VEED/fal.ai lip-sync video is wired in, the placeholder is the
 * still headshot with a subtle Ken Burns drift so it doesn't look frozen.
 */

export const AVATAR_TOP = 1152; // top of bottom 40% of 1920
export const AVATAR_HEIGHT = 1920 - AVATAR_TOP; // 768
/** Captions should clear the top of the avatar by ~20px. */
export const AVATAR_TOP_PADDING = 20;

type Props = {
  /** Still headshot path inside /public. */
  imageSrc?: string;
  /** Optional lip-synced VEED video path inside /public. */
  videoSrc?: string;
  /** Hide for scenes that need the full canvas. */
  visible?: boolean;
};

export const AvatarTalkingHead: React.FC<Props> = ({
  imageSrc = "avatar/avatar-source.png",
  videoSrc,
  visible = true,
}) => {
  const frame = useCurrentFrame();

  if (!visible) return null;

  // Subtle Ken Burns: tiny scale drift + tiny horizontal pan so the still
  // doesn't look frozen. Amplitude is small enough to read as natural micro-
  // movement (think: a person leaning slightly).
  const kbScale = 1.02 + Math.sin(frame * 0.01) * 0.012;
  const kbX = Math.sin(frame * 0.008 + 1.2) * 6;
  const kbY = Math.sin(frame * 0.006) * 4;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Talking-head region */}
      <div
        style={{
          position: "absolute",
          top: AVATAR_TOP,
          left: 0,
          width: 1080,
          height: AVATAR_HEIGHT,
          overflow: "hidden",
          background: "#0a0a0a",
        }}
      >
        {videoSrc ? (
          <Video
            src={staticFile(videoSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center 30%",
            }}
          />
        ) : (
          <Img
            src={staticFile(imageSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              // Show face high in the frame; chest sits where captions overlay
              objectPosition: "center 25%",
              transform: `scale(${kbScale}) translate(${kbX}px, ${kbY}px)`,
              transformOrigin: "center 30%",
            }}
          />
        )}

        {/* Bottom vignette so captions read over the chest area */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%)",
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Soft separator at the seam between visual and avatar.
          Just a 24px gradient so the cut feels intentional, not abrupt. */}
      <div
        style={{
          position: "absolute",
          top: AVATAR_TOP - 24,
          left: 0,
          width: 1080,
          height: 24,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.18) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
