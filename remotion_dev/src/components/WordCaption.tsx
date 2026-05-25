import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Props = {
  text: string;
  accentColor: string;
};

const WORD_INTERVAL = 6; // frames between word reveals — punchy TikTok-style cadence

export const WordCaption: React.FC<Props> = ({ text, accentColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(/\s+/).filter(Boolean);

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "16px 22px",
        fontFamily,
      }}
    >
      {words.map((word, i) => {
        const start = i * WORD_INTERVAL;
        const reveal = spring({
          frame: frame - start,
          fps,
          config: { damping: 10, stiffness: 200, mass: 0.4 },
        });
        const opacity = interpolate(frame, [start, start + 4], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const scale = 0.6 + reveal * 0.4;
        const isAccent = word.replace(/[.,!?]/g, "").length >= 7;

        return (
          <span
            key={`${word}-${i}`}
            style={{
              display: "inline-block",
              fontSize: 96,
              fontWeight: 900,
              color: isAccent ? accentColor : "white",
              textTransform: "uppercase",
              letterSpacing: -2,
              transform: `scale(${scale})`,
              opacity,
              textShadow: "0 6px 24px rgba(0,0,0,0.85)",
              WebkitTextStroke: "2px rgba(0,0,0,0.4)",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
