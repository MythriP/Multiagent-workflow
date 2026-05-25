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
  title: string;
  subtitle?: string;
  /** Annotation pill on top right */
  callout?: { label: string; value: string; color: string };
};

const TC_GREEN = "#0E9F4F";
const GEMINI_BLUE = "#4285F4";

/**
 * Line chart that shows Gemini downloads spiking 4× after Nano Banana launch.
 * Two lines: Gemini (the spike) and a flat ChatGPT baseline.
 * X axis: -28 days to +28 days, 0 = launch.
 */
export const LineChartScene: React.FC<Props> = ({
  title,
  subtitle,
  callout = { label: "Gemini Nano Banana", value: "+22M downloads", color: GEMINI_BLUE },
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleReveal = spring({ frame, fps, config: { damping: 14, stiffness: 130 } });

  const CHART_X = 100;
  const CHART_Y = 460;
  const CHART_W = 880;
  const CHART_H = 900;

  // Gemini line: low baseline, then sharp spike at launch, plateaus high
  // Sample 60 points from -28 to +28 days
  const geminiPoints: { x: number; y: number }[] = [];
  for (let i = 0; i <= 60; i++) {
    const day = -28 + (i / 60) * 56;
    let v: number;
    if (day < 0) v = 0.15 + Math.sin(i * 0.7) * 0.04; // baseline noise
    else if (day < 5) v = 0.15 + (day / 5) * 0.65; // sharp climb
    else v = 0.78 + Math.sin(i * 0.5) * 0.07; // plateau with wave
    geminiPoints.push({
      x: CHART_X + (i / 60) * CHART_W,
      y: CHART_Y + CHART_H * (1 - v),
    });
  }

  // ChatGPT baseline: flat low
  const chatgptPoints: { x: number; y: number }[] = [];
  for (let i = 0; i <= 60; i++) {
    const v = 0.18 + Math.sin(i * 0.4) * 0.025;
    chatgptPoints.push({
      x: CHART_X + (i / 60) * CHART_W,
      y: CHART_Y + CHART_H * (1 - v),
    });
  }

  // Stroke draw progress
  const drawProgress = interpolate(frame, [25, 80], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Build SVG paths up to drawProgress
  const buildPath = (pts: { x: number; y: number }[], progress: number) => {
    const lastIdx = Math.max(1, Math.floor(pts.length * progress));
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < lastIdx; i++) {
      d += ` L ${pts[i].x} ${pts[i].y}`;
    }
    return d;
  };

  const calloutReveal = spring({
    frame: frame - 80,
    fps,
    config: { damping: 12, stiffness: 180, mass: 0.5 },
  });

  // Launch marker line "Day 0"
  const markerOpacity = interpolate(frame, [40, 60], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ background: "white", padding: 60 }}>
      {/* Title */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 60,
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
            fontSize: 32,
            color: "#666",
            marginTop: 14,
            opacity: titleReveal,
          }}
        >
          {subtitle}
        </div>
      )}

      {/* SVG chart */}
      <svg
        style={{ position: "absolute", top: 0, left: 0 }}
        width={1080}
        height={1920}
      >
        {/* Y-axis labels */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((v, i) => (
          <text
            key={i}
            x={CHART_X - 14}
            y={CHART_Y + CHART_H * (1 - v) + 8}
            fontFamily={fontFamily}
            fontSize={20}
            fontWeight={600}
            textAnchor="end"
            fill="#999"
            opacity={titleReveal}
          >
            {v === 0 ? "0" : `${Math.round(v * 25)}M`}
          </text>
        ))}

        {/* X-axis baseline */}
        <line
          x1={CHART_X}
          y1={CHART_Y + CHART_H}
          x2={CHART_X + CHART_W}
          y2={CHART_Y + CHART_H}
          stroke="#0a0a0a"
          strokeWidth={3}
          opacity={titleReveal}
        />

        {/* Vertical "Day 0 — launch" marker */}
        <line
          x1={CHART_X + CHART_W / 2}
          y1={CHART_Y}
          x2={CHART_X + CHART_W / 2}
          y2={CHART_Y + CHART_H}
          stroke="#999"
          strokeWidth={2}
          strokeDasharray="8 8"
          opacity={markerOpacity * 0.6}
        />
        <text
          x={CHART_X + CHART_W / 2}
          y={CHART_Y - 14}
          fontFamily={fontFamily}
          fontSize={22}
          fontWeight={800}
          textAnchor="middle"
          fill="#0a0a0a"
          opacity={markerOpacity}
        >
          ↓ MODEL LAUNCH
        </text>

        {/* ChatGPT flat line */}
        <path
          d={buildPath(chatgptPoints, drawProgress)}
          fill="none"
          stroke="#999"
          strokeWidth={5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Gemini spike line */}
        <path
          d={buildPath(geminiPoints, drawProgress)}
          fill="none"
          stroke={callout.color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Filled area under Gemini for emphasis */}
        {drawProgress > 0.1 && (
          <path
            d={
              buildPath(geminiPoints, drawProgress) +
              ` L ${geminiPoints[Math.floor(geminiPoints.length * drawProgress) - 1].x} ${CHART_Y + CHART_H} L ${geminiPoints[0].x} ${CHART_Y + CHART_H} Z`
            }
            fill={callout.color}
            opacity={0.12}
          />
        )}

        {/* X-axis labels */}
        <text x={CHART_X} y={CHART_Y + CHART_H + 36} fontFamily={fontFamily} fontSize={20} fontWeight={700} fill="#999" opacity={titleReveal}>
          -28 DAYS
        </text>
        <text x={CHART_X + CHART_W / 2} y={CHART_Y + CHART_H + 36} fontFamily={fontFamily} fontSize={20} fontWeight={700} textAnchor="middle" fill="#999" opacity={titleReveal}>
          DAY 0
        </text>
        <text x={CHART_X + CHART_W} y={CHART_Y + CHART_H + 36} fontFamily={fontFamily} fontSize={20} fontWeight={700} textAnchor="end" fill="#999" opacity={titleReveal}>
          +28 DAYS
        </text>

        {/* Legend dots */}
        <circle cx={CHART_X + 14} cy={CHART_Y - 60} r={10} fill={callout.color} opacity={titleReveal} />
        <text x={CHART_X + 36} y={CHART_Y - 52} fontFamily={fontFamily} fontSize={26} fontWeight={800} fill="#0a0a0a" opacity={titleReveal}>
          Gemini Nano Banana
        </text>
        <circle cx={CHART_X + 360} cy={CHART_Y - 60} r={10} fill="#999" opacity={titleReveal} />
        <text x={CHART_X + 382} y={CHART_Y - 52} fontFamily={fontFamily} fontSize={26} fontWeight={800} fill="#666" opacity={titleReveal}>
          ChatGPT (baseline)
        </text>
      </svg>

      {/* Big spike callout */}
      <div
        style={{
          position: "absolute",
          right: 60,
          bottom: 200,
          background: callout.color,
          padding: "22px 36px",
          borderRadius: 16,
          color: "white",
          fontFamily,
          textAlign: "right",
          opacity: calloutReveal,
          transform: `scale(${0.7 + calloutReveal * 0.3}) rotate(${interpolate(calloutReveal, [0, 1], [-3, -2])}deg)`,
          boxShadow: `0 12px 40px ${callout.color}77`,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 26, opacity: 0.85, letterSpacing: 1, textTransform: "uppercase" }}>
          {callout.label}
        </div>
        <div style={{ fontWeight: 900, fontSize: 64, letterSpacing: -1, lineHeight: 1 }}>
          {callout.value}
        </div>
      </div>

      {/* Source */}
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
