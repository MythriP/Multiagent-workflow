import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

export const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const lineOneReveal = spring({ frame, fps, config: { damping: 14, stiffness: 120 } });
  const numberReveal = spring({ frame: frame - 18, fps, config: { damping: 8, stiffness: 180, mass: 0.5 } });
  const lineTwoReveal = spring({ frame: frame - 42, fps, config: { damping: 14, stiffness: 120 } });

  const numberOpacity = interpolate(frame, [18, 26], [0, 1], { extrapolateRight: "clamp" });
  const lineTwoOpacity = interpolate(frame, [42, 52], [0, 1], { extrapolateRight: "clamp" });

  const bgPulse = interpolate(frame, [0, 90], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 45%, #1c0a0a ${20 + bgPulse * 10}%, #050505 80%)`,
        justifyContent: "center",
        alignItems: "center",
        padding: 80,
        flexDirection: "column",
        gap: 16,
      }}
    >
      {/* Line 1 */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 88,
          color: "rgba(255,255,255,0.92)",
          textAlign: "center",
          lineHeight: 1.1,
          letterSpacing: -2,
          transform: `translateY(${interpolate(lineOneReveal, [0, 1], [60, 0])}px)`,
          opacity: interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        Image AI is beating chatbots.
      </div>

      {/* The 6.5× big number */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 260,
          color: "#FF3D3D",
          lineHeight: 0.9,
          letterSpacing: -8,
          transform: `scale(${0.5 + numberReveal * 0.5})`,
          opacity: numberOpacity,
          textShadow: "0 0 80px rgba(255,61,61,0.6)",
        }}
      >
        6.5×
      </div>

      {/* Line 2 */}
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 80,
          color: "rgba(255,255,255,0.65)",
          textAlign: "center",
          letterSpacing: -1,
          transform: `translateY(${interpolate(lineTwoReveal, [0, 1], [40, 0])}px)`,
          opacity: lineTwoOpacity,
        }}
      >
        more downloads.
      </div>

      {/* Source tag */}
      <div
        style={{
          fontFamily,
          fontSize: 32,
          color: "rgba(255,255,255,0.28)",
          letterSpacing: 2,
          marginTop: 32,
          textTransform: "uppercase",
          opacity: interpolate(frame, [60, 80], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        Appfigures · TechCrunch
      </div>
    </AbsoluteFill>
  );
};
