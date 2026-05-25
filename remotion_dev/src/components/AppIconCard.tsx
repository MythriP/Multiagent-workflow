import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Props = {
  /** Brand background color e.g. "#10A37F" for ChatGPT */
  brandBg: string;
  /** Logo character/emoji rendered large */
  logo: string;
  /** Brand name shown in pill below */
  name: string;
  /** Card position */
  x: number;
  y: number;
  size?: number;
  /** Slight rotation for that hand-placed feel */
  rotation?: number;
  /** When (in frames) the card should pop in */
  appearAt?: number;
  /** When the card should fade out */
  disappearAt?: number;
};

export const AppIconCard: React.FC<Props> = ({
  brandBg,
  logo,
  name,
  x,
  y,
  size = 360,
  rotation = -3,
  appearAt = 0,
  disappearAt = Infinity,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const reveal = spring({
    frame: frame - appearAt,
    fps,
    config: { damping: 9, stiffness: 200, mass: 0.5 },
  });

  const exit = frame > disappearAt
    ? interpolate(frame - disappearAt, [0, 8], [1, 0], { extrapolateRight: "clamp" })
    : 1;

  const opacity = reveal * exit;
  if (opacity < 0.01) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: size,
        opacity,
        transform: `rotate(${rotation}deg) scale(${0.6 + reveal * 0.4})`,
        transformOrigin: "center center",
        filter: `drop-shadow(0 24px 48px rgba(0,0,0,0.35))`,
      }}
    >
      {/* Card */}
      <div
        style={{
          width: size,
          height: size,
          background: brandBg,
          borderRadius: 60,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size * 0.5,
        }}
      >
        {logo}
      </div>

      {/* Name pill */}
      <div
        style={{
          marginTop: 14,
          textAlign: "center",
        }}
      >
        <span
          style={{
            display: "inline-block",
            fontFamily,
            fontWeight: 800,
            fontSize: 32,
            color: "white",
            background: "#0a0a0a",
            padding: "10px 22px",
            borderRadius: 12,
            letterSpacing: -0.5,
          }}
        >
          {name}
        </span>
      </div>
    </div>
  );
};
