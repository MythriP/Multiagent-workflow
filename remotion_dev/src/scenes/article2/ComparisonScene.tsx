import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

type Side = {
  brand: string;
  /** Kept for back-compat with existing scripts; the colored card chrome
   *  has been removed, so this is now only used as a subtle accent. */
  brandColor: string;
  emoji: string;
  /** Big number / phrase, e.g. "$70M" or "Jailbroken". */
  value: string;
  /** Supporting line, e.g. "in 28 days" or "reported April 2026". */
  unit: string;
};

type Props = {
  title: string;
  left: Side;
  right: Side;
  /** Optional multiplier callout, e.g. { number: "386×", label: "MORE" }. */
  multiplier?: { number: string; label: string; color: string };
};

/**
 * ComparisonScene — full-bleed typographic redesign.
 *
 * The previous version wrapped each side in an orange rounded card, which
 * read as a generic infographic template. The new design ditches the card
 * chrome entirely: dark canvas, top-anchored title, two large-typography
 * blocks separated by a small VS medallion, and an optional multiplier
 * line. Consistent with the rest of the design system (HookCard,
 * HeadlineCard, etc.) which all anchor text to the top so the avatar bust
 * has clearance at the canvas bottom.
 */
export const ComparisonScene: React.FC<Props> = ({
  title,
  left,
  right,
  multiplier,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleReveal = spring({ frame, fps, config: { damping: 14, stiffness: 130 } });
  const leftReveal = spring({ frame: frame - 14, fps, config: { damping: 12, stiffness: 130 } });
  const vsReveal = spring({ frame: frame - 26, fps, config: { damping: 8, stiffness: 220, mass: 0.4 } });
  const rightReveal = spring({ frame: frame - 38, fps, config: { damping: 12, stiffness: 130 } });
  const multiReveal = spring({ frame: frame - 70, fps, config: { damping: 10, stiffness: 180, mass: 0.5 } });

  const renderSide = (side: Side, reveal: number, isLeft: boolean) => (
    <div
      style={{
        opacity: reveal,
        transform: `translateX(${interpolate(reveal, [0, 1], [isLeft ? -40 : 40, 0])}px)`,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        paddingLeft: 60,
        paddingRight: 60,
        width: "100%",
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 700,
          fontSize: 30,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: side.brandColor,
          opacity: 0.95,
        }}
      >
        {side.brand}
      </div>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 132,
          letterSpacing: -4,
          lineHeight: 0.95,
          color: "#ffffff",
        }}
      >
        {side.value}
      </div>
      <div
        style={{
          fontFamily,
          fontWeight: 500,
          fontSize: 34,
          letterSpacing: -0.2,
          color: "rgba(255,255,255,0.62)",
          marginTop: 6,
        }}
      >
        {side.unit}
      </div>
    </div>
  );

  return (
    <AbsoluteFill
      style={{
        background: "#0a0a0a",
        padding: "120px 0 0 0",
        flexDirection: "column",
        justifyContent: "flex-start",
      }}
    >
      {/* Title */}
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 38,
          letterSpacing: 4,
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.55)",
          textAlign: "center",
          paddingLeft: 60,
          paddingRight: 60,
          opacity: titleReveal,
          transform: `translateY(${interpolate(titleReveal, [0, 1], [-12, 0])}px)`,
          marginBottom: 50,
        }}
      >
        {title}
      </div>

      {/* Left side */}
      {renderSide(left, leftReveal, true)}

      {/* VS divider — small medallion, centered */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          margin: "44px 0 32px 0",
        }}
      >
        <div
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize: 36,
            color: "#0a0a0a",
            background: "#ffffff",
            width: 80,
            height: 80,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            letterSpacing: -1,
            transform: `scale(${vsReveal}) rotate(${interpolate(vsReveal, [0, 1], [-15, 0])}deg)`,
          }}
        >
          VS
        </div>
      </div>

      {/* Right side */}
      {renderSide(right, rightReveal, false)}

      {/* Optional multiplier callout — kept inline rather than absolute so
          it sits below both sides without colliding with the avatar. */}
      {multiplier && (
        <div
          style={{
            textAlign: "center",
            marginTop: 36,
            opacity: multiReveal,
            transform: `scale(${0.85 + multiReveal * 0.15})`,
            paddingLeft: 60,
            paddingRight: 60,
          }}
        >
          <div
            style={{
              fontFamily,
              fontWeight: 900,
              fontSize: 86,
              color: multiplier.color,
              letterSpacing: -3,
              lineHeight: 1,
            }}
          >
            {multiplier.number}
          </div>
          <div
            style={{
              fontFamily,
              fontWeight: 800,
              fontSize: 28,
              color: "rgba(255,255,255,0.65)",
              letterSpacing: 4,
              textTransform: "uppercase",
              marginTop: 8,
            }}
          >
            {multiplier.label}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};
