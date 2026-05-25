import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

const W = 1080;
const H = 1920;

type FocusPoint = {
  /** Pixel coords in the 1080x1920 canvas */
  x: number;
  y: number;
  /** Scale at this point (1.0 = normal). */
  scale: number;
};

type Props = {
  /** Screenshot path (within /public). Must already be 1080x1920. */
  src: string;
  /** Background tint behind the image. */
  background?: string;
  /**
   * Sequence of focus points. Each `atFrame` is in scene-local frames.
   * The wrapper interpolates camera position + scale between consecutive
   * waypoints with ease-in-out. Children (highlights, cursors, chips)
   * are transformed together so they stay glued to the underlying UI.
   */
  camera?: { atFrame: number; focus: FocusPoint }[];
  /** Subtle continuous breathing scale (multiplicative) when no camera moves. */
  breathing?: number; // amplitude, e.g. 0.012
};

const easeInOut = (t: number) =>
  t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

/**
 * A scene wrapper that renders a 1080x1920 screenshot full-bleed and
 * animates a "camera" (scale + translate) over it. Children render in the
 * same transformed space, so highlight boxes and cursors stay aligned to
 * the underlying UI even during pan/zoom.
 */
export const ZoomScene: React.FC<React.PropsWithChildren<Props>> = ({
  src,
  background = "#FAF6E8",
  camera,
  breathing = 0.012,
  children,
}) => {
  const frame = useCurrentFrame();

  // Default camera = static center @ scale 1
  let fx = W / 2;
  let fy = H / 2;
  let scale = 1;

  if (camera && camera.length > 0) {
    if (frame <= camera[0].atFrame) {
      fx = camera[0].focus.x;
      fy = camera[0].focus.y;
      scale = camera[0].focus.scale;
    } else if (frame >= camera[camera.length - 1].atFrame) {
      const last = camera[camera.length - 1].focus;
      fx = last.x;
      fy = last.y;
      scale = last.scale;
    } else {
      for (let i = 0; i < camera.length - 1; i++) {
        const a = camera[i];
        const b = camera[i + 1];
        if (frame >= a.atFrame && frame < b.atFrame) {
          const t = interpolate(frame, [a.atFrame, b.atFrame], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const e = easeInOut(t);
          fx = interpolate(e, [0, 1], [a.focus.x, b.focus.x]);
          fy = interpolate(e, [0, 1], [a.focus.y, b.focus.y]);
          scale = interpolate(e, [0, 1], [a.focus.scale, b.focus.scale]);
          break;
        }
      }
    }
  }

  // Ambient breathing (only when no aggressive zoom is active)
  const breathe = scale < 1.1 ? 1 + Math.sin(frame * 0.012) * breathing : 1;
  const finalScale = scale * breathe;

  // Translate so the (fx, fy) point in canvas coords stays at the canvas center
  // (after scaling). At scale=1 the image already covers the canvas, so center=
  // (W/2, H/2). After scaling around the canvas center, point (fx, fy) moves to
  // (W/2 + (fx - W/2)*scale). To bring it back to center, translate by
  // -(fx - W/2)*scale. Same for y.
  const tx = -(fx - W / 2) * finalScale;
  const ty = -(fy - H / 2) * finalScale;

  return (
    <AbsoluteFill style={{ background, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: W,
          height: H,
          transform: `translate(${tx}px, ${ty}px) scale(${finalScale})`,
          transformOrigin: "50% 50%",
        }}
      >
        <Img
          src={staticFile(src)}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: W,
            height: H,
            objectFit: "cover",
          }}
        />
        {children}
      </div>
    </AbsoluteFill>
  );
};
