import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type Props = {
  /** Path within /public, e.g. "images/pinch/cropped/shot-4-portrait.png" */
  src: string;
  /**
   * Optional pan/zoom focus point. The image zooms toward (focusX, focusY)
   * in normalized [0,1] coords (0,0 = top-left, 1,1 = bottom-right) and ends
   * at `endScale` by `zoomDoneAt` frames into the scene.
   */
  focus?: {
    x: number;
    y: number;
    startScale?: number;
    endScale?: number;
    zoomDoneAt?: number;
  };
  /** Background tint behind the image */
  background?: string;
  /** Add a subtle drift even without a zoom target (Ken Burns) */
  kenBurns?: boolean;
};

/**
 * Renders a screenshot full-canvas. Children render on top so callers can
 * place cursors / highlights / chips relative to the same coordinate system
 * as the image (1080x1920).
 *
 * IMPORTANT: pre-crop screenshots to 9:16 (we have 1080x1920 portraits in
 * /public/images/pinch/cropped/). The image will be displayed at native
 * size and then scaled.
 */
export const ScreenshotShowcase: React.FC<React.PropsWithChildren<Props>> = ({
  src,
  focus,
  background = "white",
  kenBurns = false,
  children,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames: _ } = useVideoConfig();

  const startScale = focus?.startScale ?? 1.0;
  const endScale = focus?.endScale ?? (focus ? 1.4 : 1.05);
  const zoomDoneAt = focus?.zoomDoneAt ?? 60;

  // ease-out
  const t = interpolate(frame, [0, zoomDoneAt], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eased = 1 - Math.pow(1 - t, 2.2);

  const scale = interpolate(eased, [0, 1], [startScale, endScale]);

  // Center default; pan toward focus
  const fx = focus?.x ?? 0.5;
  const fy = focus?.y ?? 0.5;
  const panX = interpolate(eased, [0, 1], [0.5, fx]);
  const panY = interpolate(eased, [0, 1], [0.5, fy]);

  // Optional ken-burns drift
  const drift = kenBurns ? Math.sin(frame * 0.012) * 0.6 : 0;

  return (
    <AbsoluteFill style={{ background, overflow: "hidden" }}>
      <Img
        src={staticFile(src)}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: `${panX * 100}% ${panY * 100}%`,
          transform: `scale(${scale + drift / 100})`,
          transformOrigin: `${panX * 100}% ${panY * 100}%`,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};
