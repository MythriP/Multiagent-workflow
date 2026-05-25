import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

type Props = {
  from: number;
  to: number;
  /** Frames over which to count */
  durationInFrames?: number;
  /** Frame to start the count */
  startAt?: number;
  prefix?: string;
  suffix?: string;
  /** Number of decimals */
  decimals?: number;
  /** Format with thousands separators */
  format?: "plain" | "comma" | "compact";
  style?: React.CSSProperties;
};

const compact = (n: number) => {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
};

export const CountUp: React.FC<Props> = ({
  from,
  to,
  durationInFrames = 30,
  startAt = 0,
  prefix = "",
  suffix = "",
  decimals = 0,
  format = "comma",
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps: _ } = useVideoConfig();

  const t = interpolate(frame, [startAt, startAt + durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // ease-out cubic
  const eased = 1 - Math.pow(1 - t, 3);
  const value = from + (to - from) * eased;

  let display: string;
  if (format === "compact") display = compact(value);
  else if (format === "comma") display = value.toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
  else display = value.toFixed(decimals);

  return (
    <span style={style}>
      {prefix}
      {display}
      {suffix}
    </span>
  );
};
