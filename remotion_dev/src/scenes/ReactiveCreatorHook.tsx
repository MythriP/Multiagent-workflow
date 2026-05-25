// ReactiveCreatorHook — Phase B hook variant for non-split-screen vibes.
//
// Layout: a single full-canvas background (Veo cinematic clip or Pexels
// b-roll fallback) with a bold editorial subtitle pinned to the bottom
// third. No 50/50 split, no avatar slot. The opening 3–5 seconds reads
// as a "title card" over a moving cinematic background — the look of a
// reactive-creator / news-clip hook.
//
// This component is selected when the active vibe's `hook_variant` is
// "reactive_creator". The "split_50_50" variant uses HookCard.
//
// Motion: background fades in (no scale pulse — flat). The hook text
// snap-slides in from the bottom, the subtitle slides in just behind it.
// No glow, no shadow.

import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { VibeProfile } from "../DynamicReel";
import { MixedTypeText } from "../components/MixedTypeText";
import { isVideoSrc, resolveSrc } from "./_mediaHelpers";

type Props = {
  hook: string;
  subtitle: string;
  accentColor: string;
  /** Background media. Veo clip preferred; falls back to Pexels b-roll.
   *  When absent we drop down to the vibe primary_bg as a solid color. */
  bgMediaSrc?: string;
  vibe?: VibeProfile | null;
};

export const ReactiveCreatorHook: React.FC<Props> = ({
  hook,
  subtitle,
  accentColor,
  bgMediaSrc,
  vibe,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const bg = vibe?.color_palette.primary_bg ?? "#0a0a0a";
  const textColor = vibe?.color_palette.text_primary ?? "#ffffff";

  // Background fades in over 6 frames.
  const bgOpacity = interpolate(frame, [0, 6], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Hook text snap-slides in from the bottom.
  const hookEntry = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 220, mass: 0.6 },
  });
  const hookY = interpolate(hookEntry, [0, 1], [80, 0]);
  const hookOpacity = hookEntry;

  // Subtitle trails 4 frames behind the hook.
  const subEntry = spring({
    frame: frame - 4,
    fps,
    config: { damping: 16, stiffness: 220, mass: 0.6 },
  });
  const subY = interpolate(subEntry, [0, 1], [40, 0]);
  const subOpacity = subEntry;

  // Italicise the last 1–2 words of the hook for the editorial accent.
  const tokens = hook.trim().split(/\s+/);
  const italicWords =
    tokens.length >= 3 ? tokens.slice(-2) : tokens.slice(-1);

  return (
    <AbsoluteFill style={{ background: bg, overflow: "hidden" }}>
      {/* Full-canvas background */}
      {bgMediaSrc ? (
        <div style={{ position: "absolute", inset: 0, opacity: bgOpacity }}>
          {isVideoSrc(bgMediaSrc) ? (
            <OffthreadVideo
              src={resolveSrc(bgMediaSrc)}
              muted
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <Img
              src={resolveSrc(bgMediaSrc)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          )}
          {/* Solid bottom-third scrim so the hook text stays readable. No
              gradient — Phase B forbids them. A flat rgba block over
              roughly the bottom 40% of the canvas does the same job. */}
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              height: 820,
              background: "rgba(0,0,0,0.55)",
            }}
          />
        </div>
      ) : null}

      {/* Hook text — pinned to the bottom third */}
      <div
        style={{
          position: "absolute",
          left: 60,
          right: 60,
          bottom: 320,
          transform: `translateY(${hookY}px)`,
          opacity: hookOpacity,
        }}
      >
        <MixedTypeText
          text={hook}
          italicWords={italicWords}
          size={108}
          color={textColor}
          italicColor={accentColor}
          letterSpacing={-2.5}
          lineHeight={1.0}
          align="left"
          uppercaseSans
        />
      </div>

      {/* Subtitle — sits just under the hook, smaller, accent color */}
      {subtitle ? (
        <div
          style={{
            position: "absolute",
            left: 60,
            right: 60,
            bottom: 220,
            transform: `translateY(${subY}px)`,
            opacity: subOpacity,
          }}
        >
          <MixedTypeText
            text={subtitle}
            italicWords={[]}
            size={44}
            color={accentColor}
            letterSpacing={-0.5}
            lineHeight={1.15}
            align="left"
            uppercaseSans={false}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
