import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Props = {
  x: number;
  y: number;
  width?: number;
  rotation?: number;
  appearAt?: number;
  disappearAt?: number;
  /** Mockup content — e.g. a small stat card */
  children: React.ReactNode;
  background?: string;
};

/**
 * Generic floating UI card with browser-style chrome (3 dots) — used to make
 * stat cards, prompt boxes, dashboard tiles, etc. feel like real product UI.
 */
export const FloatingMockup: React.FC<Props> = ({
  x,
  y,
  width = 600,
  rotation = -4,
  appearAt = 0,
  disappearAt = Infinity,
  children,
  background = "white",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const reveal = spring({
    frame: frame - appearAt,
    fps,
    config: { damping: 10, stiffness: 160, mass: 0.6 },
  });
  const exit = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 10], [1, 0], { extrapolateRight: "clamp" })
    : 1;
  const opacity = reveal * exit;
  if (opacity < 0.01) return null;

  // gentle floating motion
  const floatY = Math.sin(frame * 0.05) * 4;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y + floatY,
        width,
        background,
        borderRadius: 28,
        boxShadow: "0 30px 80px rgba(0,0,0,0.45)",
        opacity,
        transform: `rotate(${rotation}deg) scale(${0.7 + reveal * 0.3})`,
        transformOrigin: "center center",
        overflow: "hidden",
        border: "1px solid rgba(0,0,0,0.06)",
      }}
    >
      {/* Browser-chrome bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "16px 22px",
          background: "rgba(0,0,0,0.04)",
          borderBottom: "1px solid rgba(0,0,0,0.06)",
        }}
      >
        <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#FF5F57" }} />
        <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#FEBC2E" }} />
        <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28C840" }} />
        <div
          style={{
            marginLeft: 16,
            fontFamily,
            fontSize: 18,
            color: "#999",
            fontWeight: 600,
          }}
        >
          appfigures.com
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: 32 }}>{children}</div>
    </div>
  );
};
