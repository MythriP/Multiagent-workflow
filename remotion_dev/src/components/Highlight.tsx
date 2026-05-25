import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type BoxProps = {
  /** Position + size in 1080x1920 canvas coords (top-left of the element) */
  x: number;
  y: number;
  width: number;
  height: number;
  appearAt?: number;
  disappearAt?: number;
  color?: string;
  /** Optional label rendered around the box */
  label?: string;
  labelPosition?: "above" | "below" | "left" | "right";
  thickness?: number;
};

/**
 * Selection box that anchors strictly to the (x, y) top-left of the target.
 * Uses fade-only entry (no scale) so the visible box never drifts off the
 * underlying UI element. Spring is clamped to [0, 1] to prevent overshoot.
 */
export const HighlightBox: React.FC<BoxProps> = ({
  x,
  y,
  width,
  height,
  appearAt = 0,
  disappearAt = Infinity,
  color = "#FFE066",
  label,
  labelPosition = "above",
  thickness = 6,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const revealRaw = spring({
    frame: frame - appearAt,
    fps,
    config: { damping: 200, stiffness: 100, mass: 0.5 },
  });
  const reveal = Math.min(1, Math.max(0, revealRaw));
  const fade = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 10], [1, 0], { extrapolateRight: "clamp" })
    : 1;
  const opacity = reveal * fade;
  if (opacity < 0.01) return null;

  let labelStyle: React.CSSProperties = {};
  if (label) {
    if (labelPosition === "above") {
      labelStyle = { left: x + width / 2, top: y - 64, transform: "translateX(-50%)" };
    } else if (labelPosition === "below") {
      labelStyle = { left: x + width / 2, top: y + height + 24, transform: "translateX(-50%)" };
    } else if (labelPosition === "left") {
      labelStyle = { left: x - 24, top: y + height / 2, transform: "translate(-100%, -50%)" };
    } else {
      labelStyle = { left: x + width + 24, top: y + height / 2, transform: "translateY(-50%)" };
    }
  }

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
          border: `${thickness}px solid ${color}`,
          borderRadius: 14,
          background: `${color}1f`,
          boxShadow: `0 0 28px ${color}66`,
          opacity,
          pointerEvents: "none",
          boxSizing: "border-box",
        }}
      />
      {label && (
        <div style={{ position: "absolute", ...labelStyle, opacity }}>
          <span
            style={{
              display: "inline-block",
              background: "#1F2A2E",
              color: "white",
              fontFamily,
              fontWeight: 800,
              fontSize: 30,
              padding: "10px 20px",
              borderRadius: 12,
              letterSpacing: -0.4,
              boxShadow: "0 12px 28px rgba(0,0,0,0.3)",
              whiteSpace: "nowrap",
            }}
          >
            {label}
          </span>
        </div>
      )}
    </>
  );
};

type CircleProps = {
  cx: number;
  cy: number;
  radius: number;
  appearAt?: number;
  disappearAt?: number;
  color?: string;
  /** When true, only a single brief pulse plays then fades. */
  singlePulse?: boolean;
};

/**
 * Pulse ring around a circular UI element. Static ring is drawn at exact
 * (cx, cy, radius) — never scaled — so it stays glued to the target. The
 * pulsing ring expands outward but is a separate, additive layer.
 */
export const HighlightCircle: React.FC<CircleProps> = ({
  cx,
  cy,
  radius,
  appearAt = 0,
  disappearAt = Infinity,
  color = "#FFE066",
  singlePulse = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sinceAppear = frame - appearAt;
  const revealRaw = spring({
    frame: sinceAppear,
    fps,
    config: { damping: 200, stiffness: 110, mass: 0.5 },
  });
  const reveal = Math.min(1, Math.max(0, revealRaw));
  const fade = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 10], [1, 0], { extrapolateRight: "clamp" })
    : 1;
  const opacity = reveal * fade;
  if (opacity < 0.01) return null;

  let pulseScale: number;
  let pulseOpacity: number;
  if (singlePulse) {
    const t = Math.min(1, Math.max(0, sinceAppear / 32));
    pulseScale = 1 + t * 0.7;
    pulseOpacity = (1 - t) * 0.7;
  } else {
    const pulseT = ((sinceAppear) / 32) % 1;
    pulseScale = 1 + pulseT * 0.6;
    pulseOpacity = (1 - pulseT) * 0.65;
  }

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: cx - radius,
          top: cy - radius,
          width: radius * 2,
          height: radius * 2,
          borderRadius: "50%",
          border: `5px solid ${color}`,
          background: `${color}1a`,
          opacity,
          boxShadow: `0 0 28px ${color}66`,
          pointerEvents: "none",
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: cx - radius * pulseScale,
          top: cy - radius * pulseScale,
          width: radius * 2 * pulseScale,
          height: radius * 2 * pulseScale,
          borderRadius: "50%",
          border: `4px solid ${color}`,
          opacity: opacity * pulseOpacity,
          pointerEvents: "none",
          boxSizing: "border-box",
        }}
      />
    </>
  );
};

type ArrowProps = {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  appearAt?: number;
  disappearAt?: number;
  color?: string;
  label?: string;
};

export const HighlightArrow: React.FC<ArrowProps> = ({
  fromX,
  fromY,
  toX,
  toY,
  appearAt = 0,
  disappearAt = Infinity,
  color = "#1F2A2E",
  label,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const revealRaw = spring({
    frame: frame - appearAt,
    fps,
    config: { damping: 200, stiffness: 110, mass: 0.5 },
  });
  const reveal = Math.min(1, Math.max(0, revealRaw));
  const fade = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 10], [1, 0], { extrapolateRight: "clamp" })
    : 1;
  const opacity = reveal * fade;
  if (opacity < 0.01) return null;

  const midX = (fromX + toX) / 2;
  const midY = (fromY + toY) / 2;
  const dx = toX - fromX;
  const dy = toY - fromY;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const cx = midX - (dy / len) * 80;
  const cy = midY + (dx / len) * 80;

  const pathLen = len + 100;
  const dashOffset = (1 - reveal) * pathLen;
  const angle = (Math.atan2(toY - cy, toX - cx) * 180) / Math.PI;

  return (
    <svg
      width={1080}
      height={1920}
      style={{ position: "absolute", inset: 0, opacity, pointerEvents: "none" }}
    >
      <path
        d={`M ${fromX} ${fromY} Q ${cx} ${cy} ${toX} ${toY}`}
        fill="none"
        stroke={color}
        strokeWidth={6}
        strokeLinecap="round"
        strokeDasharray={pathLen}
        strokeDashoffset={dashOffset}
      />
      <g transform={`translate(${toX} ${toY}) rotate(${angle})`}>
        <polygon points="0,0 -22,-12 -22,12" fill={color} />
      </g>
      {label && (
        <g>
          <rect x={fromX - 120} y={fromY - 60} width={240} height={48} rx={12} fill="#1F2A2E" />
          <text
            x={fromX}
            y={fromY - 28}
            textAnchor="middle"
            fontSize={26}
            fontWeight={800}
            fill="white"
            fontFamily={fontFamily}
          >
            {label}
          </text>
        </g>
      )}
    </svg>
  );
};
