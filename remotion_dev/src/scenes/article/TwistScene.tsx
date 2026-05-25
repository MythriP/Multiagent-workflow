import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

export const TwistScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const lineOne = spring({ frame, fps, config: { damping: 12, stiffness: 140 } });
  const symbol = spring({ frame: frame - 20, fps, config: { damping: 6, stiffness: 240, mass: 0.3 } });
  const lineTwo = spring({ frame: frame - 36, fps, config: { damping: 12, stiffness: 120 } });

  const scanX = interpolate(frame, [0, 90], [-1080, 1080]);

  return (
    <AbsoluteFill
      style={{
        background: "#08050a",
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        padding: 80,
        gap: 20,
        overflow: "hidden",
      }}
    >
      {/* Scan line effect */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          width: 3,
          background: "linear-gradient(to bottom, transparent, rgba(180,100,255,0.6), transparent)",
          left: `${((frame * 11) % 1080)}px`,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 92,
          color: "rgba(255,255,255,0.85)",
          textAlign: "center",
          letterSpacing: -2,
          transform: `translateY(${interpolate(lineOne, [0, 1], [50, 0])}px)`,
          opacity: lineOne,
        }}
      >
        But here's the thing.
      </div>

      {/* ≠ symbol */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 320,
          color: "#CC44FF",
          lineHeight: 0.85,
          transform: `scale(${0.4 + symbol * 0.6}) rotate(${interpolate(symbol, [0, 1], [-20, 0])}deg)`,
          opacity: symbol,
          textShadow: "0 0 100px rgba(200,68,255,0.5)",
        }}
      >
        ≠
      </div>

      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 92,
          color: "rgba(255,255,255,0.85)",
          textAlign: "center",
          letterSpacing: -2,
          transform: `translateY(${interpolate(lineTwo, [0, 1], [50, 0])}px)`,
          opacity: lineTwo,
        }}
      >
        Downloads ≠ Money.
      </div>

      <div
        style={{
          marginTop: 30,
          fontFamily,
          fontWeight: 600,
          fontSize: 44,
          color: "rgba(255,255,255,0.3)",
          textAlign: "center",
          opacity: interpolate(frame, [55, 75], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        The data proves it ↓
      </div>
    </AbsoluteFill>
  );
};
