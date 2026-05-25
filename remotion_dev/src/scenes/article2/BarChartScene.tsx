import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

export type Bar = {
  label: string;
  value: number;        // raw value
  formatted: string;    // display string e.g. "$70M"
  color: string;
  highlight?: boolean;  // if true, highlight after grow
};

type Props = {
  title: string;
  subtitle?: string;
  yAxisLabel?: string;
  bars: Bar[];
  accentColor?: string;
};

const TC_GREEN = "#0E9F4F";

export const BarChartScene: React.FC<Props> = ({
  title,
  subtitle,
  yAxisLabel,
  bars,
  accentColor = TC_GREEN,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Title in
  const titleReveal = spring({ frame, fps, config: { damping: 14, stiffness: 130 } });
  const subtitleReveal = spring({ frame: frame - 10, fps, config: { damping: 14, stiffness: 130 } });

  // Each bar grows in sequence
  const BAR_START = 30;
  const BAR_DURATION = 22;
  const BAR_STAGGER = 8;

  const maxValue = Math.max(...bars.map((b) => b.value));

  const CHART_W = 920;
  const CHART_H = 1000;
  const CHART_TOP = 380;
  const CHART_LEFT = (1080 - CHART_W) / 2;
  const BAR_WIDTH = (CHART_W / bars.length) * 0.7;
  const BAR_GAP = (CHART_W / bars.length) * 0.3;

  return (
    <AbsoluteFill style={{ background: "white", padding: 60, flexDirection: "column" }}>
      {/* Title */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 64,
          color: "#0a0a0a",
          letterSpacing: -1.5,
          lineHeight: 1.1,
          opacity: titleReveal,
          transform: `translateY(${interpolate(titleReveal, [0, 1], [-20, 0])}px)`,
        }}
      >
        {title}
      </div>

      {subtitle && (
        <div
          style={{
            fontFamily,
            fontWeight: 600,
            fontSize: 34,
            color: "#666",
            marginTop: 14,
            opacity: subtitleReveal,
          }}
        >
          {subtitle}
        </div>
      )}

      {/* Chart area */}
      <div
        style={{
          position: "absolute",
          left: CHART_LEFT,
          top: CHART_TOP,
          width: CHART_W,
          height: CHART_H,
        }}
      >
        {/* Y-axis label */}
        {yAxisLabel && (
          <div
            style={{
              position: "absolute",
              left: -40,
              top: -10,
              fontFamily,
              fontWeight: 700,
              fontSize: 28,
              color: "#999",
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            {yAxisLabel}
          </div>
        )}

        {/* Baseline */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 80,
            height: 3,
            background: "#0a0a0a",
            opacity: titleReveal,
          }}
        />

        {/* Bars */}
        {bars.map((bar, i) => {
          const start = BAR_START + i * BAR_STAGGER;
          const grow = spring({
            frame: frame - start,
            fps,
            durationInFrames: BAR_DURATION,
            config: { damping: 14, stiffness: 90, mass: 0.7 },
          });
          const height = (bar.value / maxValue) * (CHART_H - 200) * grow;

          // Highlight pulse for the standout bar
          const highlightStart = start + BAR_DURATION + 6;
          const pulse = bar.highlight
            ? 1 + 0.04 * Math.sin((frame - highlightStart) * 0.18)
            : 1;
          const isPulsing = bar.highlight && frame > highlightStart;

          // Value label opacity
          const labelOpacity = interpolate(
            frame,
            [start + BAR_DURATION - 4, start + BAR_DURATION + 6],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          const x = i * (BAR_WIDTH + BAR_GAP) + BAR_GAP / 2;

          return (
            <div key={i}>
              {/* Bar */}
              <div
                style={{
                  position: "absolute",
                  left: x,
                  bottom: 80,
                  width: BAR_WIDTH,
                  height: Math.max(0, height),
                  background: bar.color,
                  borderRadius: "8px 8px 0 0",
                  transform: `scale(${pulse})`,
                  transformOrigin: "bottom center",
                }}
              />

              {/* Value above bar */}
              <div
                style={{
                  position: "absolute",
                  left: x,
                  bottom: 80 + height + 16,
                  width: BAR_WIDTH,
                  fontFamily,
                  fontWeight: 900,
                  fontSize: bar.highlight ? 56 : 36,
                  color: bar.highlight ? bar.color : "#0a0a0a",
                  textAlign: "center",
                  opacity: labelOpacity,
                  letterSpacing: -1,
                }}
              >
                {bar.formatted}
              </div>

              {/* Bar label */}
              <div
                style={{
                  position: "absolute",
                  left: x - 10,
                  bottom: 0,
                  width: BAR_WIDTH + 20,
                  fontFamily,
                  fontWeight: 700,
                  fontSize: 22,
                  color: bar.highlight ? bar.color : "#666",
                  textAlign: "center",
                  lineHeight: 1.2,
                  opacity: labelOpacity,
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                {bar.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* Source watermark */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          right: 60,
          fontFamily,
          fontWeight: 700,
          fontSize: 22,
          color: "#bbb",
          letterSpacing: 1.5,
          textTransform: "uppercase",
        }}
      >
        Source · Appfigures
      </div>
    </AbsoluteFill>
  );
};
