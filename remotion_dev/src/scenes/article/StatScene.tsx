import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Props = {
  brand: string;
  brandColor: string;
  logoChar: string;
  statNumber: string;
  statUnit: string;
  descriptor: string;
  subline: string;
};

export const StatScene: React.FC<Props> = ({
  brand,
  brandColor,
  logoChar,
  statNumber,
  statUnit,
  descriptor,
  subline,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const chipReveal = spring({ frame, fps, config: { damping: 12, stiffness: 200, mass: 0.4 } });
  const numReveal = spring({ frame: frame - 10, fps, config: { damping: 9, stiffness: 160, mass: 0.6 } });
  const textReveal = spring({ frame: frame - 28, fps, config: { damping: 14, stiffness: 120 } });
  const subReveal = interpolate(frame, [45, 60], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: "#050505",
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        padding: 80,
        gap: 28,
      }}
    >
      {/* Brand chip */}
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 42,
          color: brandColor,
          background: `${brandColor}18`,
          border: `3px solid ${brandColor}55`,
          padding: "16px 40px",
          borderRadius: 999,
          letterSpacing: 3,
          textTransform: "uppercase",
          transform: `scale(${chipReveal})`,
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <span style={{ fontSize: 48 }}>{logoChar}</span>
        {brand}
      </div>

      {/* Big stat */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 220,
          color: "white",
          lineHeight: 0.9,
          letterSpacing: -6,
          transform: `translateY(${interpolate(numReveal, [0, 1], [80, 0])}px) scale(${0.7 + numReveal * 0.3})`,
          opacity: numReveal,
          textShadow: `0 0 60px ${brandColor}44`,
        }}
      >
        {statNumber}
      </div>

      <div
        style={{
          fontFamily,
          fontWeight: 700,
          fontSize: 64,
          color: brandColor,
          letterSpacing: -1,
          textTransform: "uppercase",
          opacity: numReveal,
        }}
      >
        {statUnit}
      </div>

      {/* Descriptor */}
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 58,
          color: "rgba(255,255,255,0.8)",
          textAlign: "center",
          lineHeight: 1.2,
          letterSpacing: -1,
          transform: `translateY(${interpolate(textReveal, [0, 1], [40, 0])}px)`,
          opacity: textReveal,
        }}
      >
        {descriptor}
      </div>

      {/* Sub-line */}
      <div
        style={{
          fontFamily,
          fontWeight: 600,
          fontSize: 40,
          color: "rgba(255,255,255,0.38)",
          textAlign: "center",
          letterSpacing: 0,
          opacity: subReveal,
          transform: `translateY(${interpolate(subReveal, [0, 1], [20, 0])}px)`,
        }}
      >
        {subline}
      </div>

      {/* Bottom accent bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 8,
          background: brandColor,
          opacity: 0.7,
          boxShadow: `0 0 40px ${brandColor}`,
          transform: `scaleX(${interpolate(frame, [0, 60], [0, 1], { extrapolateRight: "clamp" })})`,
          transformOrigin: "left",
        }}
      />
    </AbsoluteFill>
  );
};
