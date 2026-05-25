import { interpolate, useCurrentFrame } from "remotion";

type Props = {
  text: string;
  /** Frames per character. Lower = faster typing. */
  charsPerFrame?: number;
  /** Frame to start typing at */
  startAt?: number;
  /** Whether to show the blinking cursor */
  cursor?: boolean;
  cursorColor?: string;
  style?: React.CSSProperties;
  className?: string;
};

/**
 * Types out text one character at a time, like a translation appearing live.
 */
export const TypewriterText: React.FC<Props> = ({
  text,
  charsPerFrame = 0.6,
  startAt = 0,
  cursor = true,
  cursorColor = "#999",
  style,
  className,
}) => {
  const frame = useCurrentFrame();
  const elapsed = Math.max(0, frame - startAt);
  const charCount = Math.floor(elapsed * charsPerFrame);
  const visible = text.slice(0, Math.min(text.length, charCount));
  const done = visible.length >= text.length;

  const cursorOpacity = done ? 0 : Math.floor(frame / 8) % 2 === 0 ? 1 : 0;

  return (
    <span style={style} className={className}>
      {visible}
      {cursor && (
        <span
          style={{
            display: "inline-block",
            width: "0.08em",
            height: "1em",
            background: cursorColor,
            marginLeft: 4,
            verticalAlign: "-0.1em",
            opacity: cursorOpacity,
          }}
        />
      )}
    </span>
  );
};
