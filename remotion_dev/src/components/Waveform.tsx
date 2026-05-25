import { useCurrentFrame } from "remotion";

type Props = {
  bars?: number;
  color?: string;
  width?: number;
  height?: number;
  /** "live" pulses constantly. "fade-out" fades out. */
  state?: "live" | "fade-out";
  fadeStart?: number;
};

/**
 * Animated voice waveform — vertical bars driven by sine waves at random
 * phases, looking like real speech audio levels.
 */
export const Waveform: React.FC<Props> = ({
  bars = 40,
  color = "#0a0a0a",
  width = 700,
  height = 160,
  state = "live",
  fadeStart = 0,
}) => {
  const frame = useCurrentFrame();
  const barWidth = width / bars / 2;

  const fadeOpacity =
    state === "fade-out"
      ? Math.max(0, 1 - Math.max(0, frame - fadeStart) / 30)
      : 1;

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {Array.from({ length: bars }).map((_, i) => {
        // Each bar has its own phase + frequency for organic feel
        const phase = i * 0.45;
        const freq = 0.18 + (i % 5) * 0.05;
        const envelope = 0.4 + 0.6 * Math.abs(Math.sin(i * 0.21));
        const amp = Math.abs(Math.sin(frame * freq + phase)) * envelope;
        const h = Math.max(6, amp * height * 0.9);
        const x = (i + 0.5) * (width / bars) - barWidth / 2;
        const y = (height - h) / 2;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={h}
            rx={barWidth / 2}
            fill={color}
            opacity={fadeOpacity}
          />
        );
      })}
    </svg>
  );
};
