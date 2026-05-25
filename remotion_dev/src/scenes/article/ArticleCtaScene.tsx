import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

export const ArticleCtaScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const lineReveal = spring({ frame, fps, config: { damping: 12, stiffness: 130 } });
  const ctaReveal = spring({ frame: frame - 28, fps, config: { damping: 10, stiffness: 200, mass: 0.4 } });
  const arrowBounce = Math.sin(frame * 0.18) * 12;

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(160deg, #0f0a1a 0%, #050505 60%)",
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        padding: 80,
        gap: 32,
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 82,
          color: "white",
          textAlign: "center",
          lineHeight: 1.1,
          letterSpacing: -2,
          transform: `translateY(${interpolate(lineReveal, [0, 1], [60, 0])}px)`,
          opacity: lineReveal,
        }}
      >
        The image model race is just getting started.
      </div>

      <div
        style={{
          width: 200,
          height: 6,
          background: "#FF3D3D",
          borderRadius: 3,
          boxShadow: "0 0 30px #FF3D3D",
          opacity: lineReveal,
          transform: `scaleX(${lineReveal})`,
        }}
      />

      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 68,
          color: "#FF3D3D",
          letterSpacing: 3,
          textTransform: "uppercase",
          transform: `scale(${0.6 + ctaReveal * 0.4})`,
          opacity: ctaReveal,
        }}
      >
        Follow for more ↓
      </div>

      <div
        style={{
          fontSize: 90,
          opacity: ctaReveal,
          transform: `translateY(${arrowBounce}px)`,
        }}
      >
        👇
      </div>

      <div
        style={{
          fontFamily,
          fontSize: 34,
          color: "rgba(255,255,255,0.25)",
          textAlign: "center",
          letterSpacing: 1,
          opacity: interpolate(frame, [60, 80], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        Source: TechCrunch · Appfigures · May 2026
      </div>
    </AbsoluteFill>
  );
};
