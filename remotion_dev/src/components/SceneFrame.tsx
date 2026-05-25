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
  /** Pixel coords inside the SOURCE 1080x1920 screenshot. */
  x: number;
  y: number;
  /** Zoom level (1 = source displayed at native px). */
  scale: number;
};

type Props = {
  /** Screenshot path inside /public. Must be 1080x1920. */
  src: string;
  /** Background tint behind the image (cream by default). */
  background?: string;
  /**
   * Height of the visible viewport in canvas pixels. Use 1920 for full-frame,
   * AVATAR_TOP (1152) when the avatar overlay covers the bottom 40%.
   */
  viewportHeight?: number;
  /**
   * Camera waypoints (scene-local frames). Each focus is a point in the
   * SOURCE screenshot that should be centered horizontally inside the
   * viewport, and centered vertically inside the viewport, at the given
   * scale. Children render in the SAME transformed space, so highlight
   * boxes / cursors stay glued to the underlying UI.
   */
  camera?: { atFrame: number; focus: FocusPoint }[];
  /** Subtle continuous breathing scale when no zoom is active. */
  breathing?: number;
};

const easeInOut = (t: number) =>
  t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

/**
 * Renders a screenshot into a viewport that sits at the top of the canvas.
 * Use `viewportHeight` to size the visible region:
 *   - 1920 = full canvas (avatar hidden)
 *   - 1152 = top 60% of canvas (avatar overlay covers bottom 40%)
 *
 * Highlights and cursors should be placed in SOURCE coordinates (the same
 * 1080x1920 space as the screenshot). They get the same camera transform
 * applied, so they stay aligned through pan/zoom.
 *
 * Default focus = (540, viewportHeight/2 mapped back to source coords),
 * scale chosen so the source region [0..viewportHeight] fits the viewport
 * exactly. In practice you'll always supply a `camera` prop.
 */
export const SceneFrame: React.FC<React.PropsWithChildren<Props>> = ({
  src,
  background = "#FAF6E8",
  viewportHeight = H,
  camera,
  breathing = 0.012,
  children,
}) => {
  const frame = useCurrentFrame();

  // Default: show the top portion of the screenshot at native scale,
  // centered horizontally, top-aligned.
  let fx = W / 2;
  let fy = viewportHeight / 2;
  let scale = 1;

  if (camera && camera.length > 0) {
    if (frame <= camera[0].atFrame) {
      ({ x: fx, y: fy, scale } = camera[0].focus);
    } else if (frame >= camera[camera.length - 1].atFrame) {
      ({ x: fx, y: fy, scale } = camera[camera.length - 1].focus);
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

  // Ambient breathing only at low zooms
  const breathe = scale < 1.1 ? 1 + Math.sin(frame * 0.012) * breathing : 1;
  const finalScale = scale * breathe;

  // We render the source 1080x1920 image inside a div that we translate so
  // the focus point (fx, fy) ends up at the center of the viewport. The
  // viewport sits at the top of the canvas (y in [0, viewportHeight]).
  // Scale around the (fx, fy) origin so children placed at source coords
  // stay glued to the image.
  const viewportCx = W / 2;
  const viewportCy = viewportHeight / 2;
  const tx = viewportCx - fx;
  const ty = viewportCy - fy;

  return (
    <AbsoluteFill style={{ background, overflow: "hidden" }}>
      {/* Clip to viewport */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: W,
          height: viewportHeight,
          overflow: "hidden",
          background,
        }}
      >
        {/* Transformed layer that holds screenshot + children, all in source coords */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: W,
            height: H,
            transform: `translate(${tx}px, ${ty}px) scale(${finalScale})`,
            transformOrigin: `${fx}px ${fy}px`,
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
      </div>
    </AbsoluteFill>
  );
};
