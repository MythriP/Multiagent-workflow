import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type CursorWaypoint = {
  /** Position in 1080x1920 canvas coords */
  x: number;
  y: number;
  /** Frame at which the cursor should arrive at this point */
  atFrame: number;
  /** Optional "click" pulse at this waypoint */
  click?: boolean;
};

type Props = {
  /** First waypoint controls when cursor enters; subsequent ones are stops. */
  path: CursorWaypoint[];
  /** Frame at which to fade out (default: never) */
  fadeOutAt?: number;
  color?: string;
};

/**
 * macOS-style arrow cursor that flies between waypoints with eased motion
 * and pulses when clicking. Renders on top of any scene at absolute coords.
 */
export const AnimatedCursor: React.FC<Props> = ({
  path,
  fadeOutAt = Infinity,
  color = "#0a0a0a",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (path.length === 0) return null;

  // Cursor enters at first waypoint's atFrame with a fly-in
  const firstFrame = path[0].atFrame;
  const enter = spring({
    frame: frame - firstFrame + 8, // start slightly before
    fps,
    config: { damping: 14, stiffness: 110, mass: 0.8 },
  });

  // Find current segment
  let x = path[0].x;
  let y = path[0].y;
  let clickPulse = 0;

  if (frame <= path[0].atFrame) {
    x = path[0].x;
    y = path[0].y;
  } else if (frame >= path[path.length - 1].atFrame) {
    const last = path[path.length - 1];
    x = last.x;
    y = last.y;
    if (last.click) {
      const sinceClick = frame - last.atFrame;
      clickPulse = sinceClick >= 0 && sinceClick < 18 ? 1 - sinceClick / 18 : 0;
    }
  } else {
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i];
      const b = path[i + 1];
      if (frame >= a.atFrame && frame < b.atFrame) {
        const t = interpolate(frame, [a.atFrame, b.atFrame], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        // ease-in-out
        const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        x = interpolate(eased, [0, 1], [a.x, b.x]);
        y = interpolate(eased, [0, 1], [a.y, b.y]);

        if (b.click) {
          const sinceArrive = frame - b.atFrame;
          if (sinceArrive >= -2 && sinceArrive < 18) {
            clickPulse = sinceArrive >= 0 ? 1 - sinceArrive / 18 : 0;
          }
        }
        break;
      }
    }
  }

  // Fade
  const fadeOpacity =
    frame >= fadeOutAt
      ? interpolate(frame - fadeOutAt, [0, 12], [1, 0], { extrapolateRight: "clamp" })
      : 1;
  const opacity = enter * fadeOpacity;

  if (opacity < 0.01) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Click pulse ring (under cursor) */}
      {clickPulse > 0 && (
        <div
          style={{
            position: "absolute",
            left: x,
            top: y,
            transform: `translate(-50%, -50%) scale(${1 + (1 - clickPulse) * 1.6})`,
            width: 80,
            height: 80,
            borderRadius: "50%",
            border: `4px solid ${color}`,
            opacity: clickPulse * 0.6,
          }}
        />
      )}
      {/* Cursor arrow */}
      <svg
        width={56}
        height={56}
        viewBox="0 0 16 16"
        style={{
          position: "absolute",
          left: x,
          top: y,
          opacity,
          transform: `translate(-2px, -2px) scale(${1 - clickPulse * 0.15})`,
          filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.25))",
        }}
      >
        <path
          d="M2 1 L2 12 L5 9 L7.5 14.5 L9.5 13.5 L7 8 L11 8 Z"
          fill={color}
          stroke="white"
          strokeWidth={0.8}
          strokeLinejoin="round"
        />
      </svg>
    </AbsoluteFill>
  );
};
