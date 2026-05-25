import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Props = {
  x: number;
  y: number;
  rotation?: number;
  appearAt?: number;
  disappearAt?: number;
  background?: string;
  color?: string;
  fontSize?: number;
  /** Scale base before spring */
  scale?: number;
  children: React.ReactNode;
  /** Slow drift in pixels for that "alive" feel */
  drift?: number;
};

/** Small badge / chip / tag floating in negative space. */
export const FloatingChip: React.FC<Props> = ({
  x,
  y,
  rotation = 0,
  appearAt = 0,
  disappearAt = Infinity,
  background = "#0a0a0a",
  color = "white",
  fontSize = 32,
  scale = 1,
  children,
  drift = 6,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const reveal = spring({
    frame: frame - appearAt,
    fps,
    config: { damping: 11, stiffness: 220, mass: 0.5 },
  });
  const exit = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 8], [1, 0], { extrapolateRight: "clamp" })
    : 1;
  const opacity = reveal * exit;
  if (opacity < 0.01) return null;

  const driftY = Math.sin((frame - appearAt) * 0.04) * drift;
  const driftX = Math.cos((frame - appearAt) * 0.03) * drift * 0.6;

  return (
    <div
      style={{
        position: "absolute",
        left: x + driftX,
        top: y + driftY,
        background,
        color,
        fontFamily,
        fontWeight: 800,
        fontSize,
        padding: `${fontSize * 0.35}px ${fontSize * 0.7}px`,
        borderRadius: fontSize * 0.45,
        opacity,
        transform: `rotate(${rotation}deg) scale(${scale * (0.6 + reveal * 0.4)})`,
        transformOrigin: "center center",
        boxShadow: "0 18px 38px rgba(0,0,0,0.35)",
        whiteSpace: "nowrap",
        letterSpacing: -0.5,
      }}
    >
      {children}
    </div>
  );
};
