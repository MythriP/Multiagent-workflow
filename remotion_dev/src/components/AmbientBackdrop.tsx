import { AbsoluteFill, Img, OffthreadVideo, staticFile } from "remotion";

type Props = {
  /** Path or URL to a video / image. Public-relative paths get wrapped with
   *  staticFile() automatically. */
  src: string;
  /** Opacity of the back layer (0..1). Defaults to 0.45 so the foreground
   *  text stays the hero. */
  opacity?: number;
  /** Final dim scrim on top of the backdrop, 0..1. Defaults to 0.55 — the
   *  text should never have to fight the back layer. */
  scrim?: number;
};

const isVideoSrc = (src: string): boolean => {
  const lowered = src.split("?")[0].toLowerCase();
  if (lowered.startsWith("data:video/")) return true;
  return /\.(mp4|webm|mov|m4v)$/.test(lowered);
};

const resolveSrc = (src: string): string => {
  if (
    src.startsWith("data:") ||
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("/")
  ) {
    return src;
  }
  return staticFile(src);
};

/**
 * Ambient blurred backdrop. Used by text-only scenes (hook, headline,
 * dramatic_word, cta) so they don't have to fall back to a flat color. The
 * media is heavily blurred + scrimmed so it reads as atmosphere, not content.
 *
 * Rule of thumb (set by the script_agent):
 *   • Pexels portrait video > blurred Pexels photo > flat black (last resort).
 */
export const AmbientBackdrop: React.FC<Props> = ({
  src,
  opacity = 0.45,
  scrim = 0.55,
}) => {
  const resolved = resolveSrc(src);
  const isVideo = isVideoSrc(src);
  return (
    <>
      <AbsoluteFill style={{ opacity }}>
        {isVideo ? (
          <OffthreadVideo
            src={resolved}
            muted
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          <Img
            src={resolved}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}
      </AbsoluteFill>
      <AbsoluteFill style={{ background: `rgba(0,0,0,${scrim})` }} />
    </>
  );
};
