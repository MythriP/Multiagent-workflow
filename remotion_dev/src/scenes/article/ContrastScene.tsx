import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

const CHATGPT_GREEN = "#10a37f";
const GEMINI_BLUE = "#4285F4";

export const ContrastScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerReveal = spring({ frame, fps, config: { damping: 14, stiffness: 130 } });
  const geminiReveal = spring({ frame: frame - 15, fps, config: { damping: 10, stiffness: 150, mass: 0.7 } });
  const chatgptReveal = spring({ frame: frame - 45, fps, config: { damping: 8, stiffness: 180, mass: 0.5 } });

  // Bar widths — proportional: ChatGPT $70M vs Gemini $181K
  const ratio = 181000 / 70000000;
  const geminiBarW = interpolate(frame, [20, 60], [0, ratio * 860], { extrapolateRight: "clamp" });
  const chatgptBarW = interpolate(frame, [50, 100], [0, 860], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: "#060606",
        flexDirection: "column",
        justifyContent: "center",
        padding: 80,
        gap: 36,
      }}
    >
      {/* Header */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 64,
          color: "rgba(255,255,255,0.7)",
          letterSpacing: -1,
          transform: `translateY(${interpolate(headerReveal, [0, 1], [-40, 0])}px)`,
          opacity: headerReveal,
        }}
      >
        Revenue in 28 days 💸
      </div>

      {/* Gemini row */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, opacity: geminiReveal }}>
        <div
          style={{
            fontFamily,
            fontWeight: 800,
            fontSize: 52,
            color: GEMINI_BLUE,
            letterSpacing: -1,
            display: "flex",
            alignItems: "center",
            gap: 20,
          }}
        >
          <span style={{ fontSize: 44 }}>🔵</span>
          Gemini
          <span style={{ fontWeight: 600, fontSize: 44, color: "rgba(255,255,255,0.55)" }}>
            $181,000
          </span>
        </div>
        {/* Bar */}
        <div style={{ background: "rgba(255,255,255,0.08)", borderRadius: 8, height: 24, overflow: "hidden" }}>
          <div
            style={{
              width: `${geminiBarW}px`,
              maxWidth: "100%",
              height: "100%",
              background: GEMINI_BLUE,
              borderRadius: 8,
              boxShadow: `0 0 20px ${GEMINI_BLUE}66`,
            }}
          />
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 2, background: "rgba(255,255,255,0.08)" }} />

      {/* ChatGPT row */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, opacity: chatgptReveal }}>
        <div
          style={{
            fontFamily,
            fontWeight: 800,
            fontSize: 52,
            color: CHATGPT_GREEN,
            letterSpacing: -1,
            display: "flex",
            alignItems: "center",
            gap: 20,
          }}
        >
          <span style={{ fontSize: 44 }}>🟢</span>
          ChatGPT
          <span style={{ fontWeight: 900, fontSize: 56, color: CHATGPT_GREEN }}>
            $70,000,000
          </span>
        </div>
        {/* Bar */}
        <div style={{ background: "rgba(255,255,255,0.08)", borderRadius: 8, height: 24, overflow: "hidden" }}>
          <div
            style={{
              width: `${chatgptBarW}px`,
              maxWidth: "100%",
              height: "100%",
              background: CHATGPT_GREEN,
              borderRadius: 8,
              boxShadow: `0 0 20px ${CHATGPT_GREEN}66`,
            }}
          />
        </div>
      </div>

      {/* Multiplier callout */}
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 68,
          color: "white",
          textAlign: "center",
          marginTop: 16,
          opacity: interpolate(frame, [80, 100], [0, 1], { extrapolateRight: "clamp" }),
          transform: `scale(${interpolate(frame, [80, 100], [0.8, 1], { extrapolateRight: "clamp" })})`,
        }}
      >
        <span style={{ color: CHATGPT_GREEN }}>386×</span> more revenue.
      </div>
    </AbsoluteFill>
  );
};
