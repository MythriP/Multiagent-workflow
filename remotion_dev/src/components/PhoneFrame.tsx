import {
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type ZoomTarget = {
  /** Normalized x of the focus center (0-1, of the rendered image) */
  x: number;
  /** Normalized y of the focus center (0-1) */
  y: number;
  /** Scale at which to zoom in */
  scale: number;
  /** Frame at which to fully zoom to this point */
  atFrame: number;
};

type Props = {
  /** static-file path within /public, e.g. "images/pinch/shot-4.png" */
  src: string;
  /** Optional Ken-Burns-style zoom target */
  zoom?: ZoomTarget;
  /** Background behind the phone */
  background?: string;
  /** Initial zoom scale (default 1.0) */
  initialScale?: number;
  /** Whether to render the phone bezel (default true) */
  bezel?: boolean;
};

/**
 * Renders a screenshot inside a vertical "phone-like" frame on a 1080x1920
 * canvas. Optionally Ken-Burns-zooms toward a focus point.
 *
 * The screenshots are 1024x576-ish landscape; they get cropped to the focus
 * region to fit a 9:16 frame.
 */
export const PhoneFrame: React.FC<Props> = ({
  src,
  zoom,
  background = "#f5f6f8",
  initialScale = 1.55,
  bezel = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Compute current zoom
  const targetAt = zoom?.atFrame ?? 30;
  const zoomT = interpolate(frame, [0, targetAt], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eased = 1 - Math.pow(1 - zoomT, 2);

  const targetScale = zoom ? interpolate(eased, [0, 1], [initialScale, zoom.scale]) : initialScale;
  const targetX = zoom ? interpolate(eased, [0, 1], [0.5, zoom.x]) : 0.5;
  const targetY = zoom ? interpolate(eased, [0, 1], [0.5, zoom.y]) : 0.5;

  // Outer phone container
  const phoneW = 980;
  const phoneH = 1740;
  const radius = 80;
  const phoneX = (1080 - phoneW) / 2;
  const phoneY = (1920 - phoneH) / 2;

  // Reveal animation
  const reveal = spring({ frame, fps, config: { damping: 14, stiffness: 110, mass: 0.8 } });

  return (
    <div style={{ position: "absolute", inset: 0, background, overflow: "hidden" }}>
      {/* Soft accent gradient */}
      <div style={{ position: "absolute", top: -200, left: -200, width: 700, height: 700, borderRadius: "50%", background: "#3D6BFE22", filter: "blur(120px)" }} />
      <div style={{ position: "absolute", bottom: -200, right: -200, width: 700, height: 700, borderRadius: "50%", background: "#FF7A4522", filter: "blur(140px)" }} />

      <div
        style={{
          position: "absolute",
          left: phoneX,
          top: phoneY,
          width: phoneW,
          height: phoneH,
          borderRadius: radius,
          overflow: "hidden",
          background: "white",
          boxShadow: bezel ? "0 50px 120px rgba(0,0,0,0.25), 0 0 0 14px #0a0a0a" : "0 30px 80px rgba(0,0,0,0.18)",
          opacity: reveal,
          transform: `translateY(${interpolate(reveal, [0, 1], [40, 0])}px)`,
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            position: "relative",
            overflow: "hidden",
            background: "white",
          }}
        >
          <Img
            src={staticFile(src)}
            style={{
              position: "absolute",
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: `${targetX * 100}% ${targetY * 100}%`,
              transform: `scale(${targetScale})`,
              transformOrigin: `${targetX * 100}% ${targetY * 100}%`,
            }}
          />
        </div>
      </div>
    </div>
  );
};
