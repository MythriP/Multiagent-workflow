import { AbsoluteFill } from "remotion";
import type { VibeProfile } from "../DynamicReel";

type Props = {
  vibe: VibeProfile;
  /** Choose "primary" (default) or "secondary" surface tone. */
  surface?: "primary" | "secondary";
  /** Kept for back-compat with callers that still pass `dotGrid`. The dot
   *  grid was a radial-gradient texture; the no-gradient rule (2026-05-13)
   *  retires it. Grain is now applied globally via <GrainOverlay/>. */
  dotGrid?: boolean;
};

/**
 * Solid backdrop driven by the vibe's color palette. Lives behind every
 * scene that doesn't pull a Pexels b-roll. Strictly a flat fill — no
 * gradient, no halo. Global grain comes from <GrainOverlay/>.
 */
export const VibeBackdrop: React.FC<Props> = ({ vibe, surface = "primary" }) => {
  const bg =
    surface === "secondary"
      ? vibe.color_palette.secondary_bg
      : vibe.color_palette.primary_bg;
  return <AbsoluteFill style={{ backgroundColor: bg }} />;
};

/**
 * Map vibe.motion_intensity to spring config. Used by all 5 new scenes so
 * "kinetic" reels feel snappier and "calm" reels glide.
 */
export const springConfigFor = (intensity: VibeProfile["motion_intensity"]) => {
  switch (intensity) {
    case "calm":
      return { damping: 22, stiffness: 70, mass: 0.9 };
    case "kinetic":
      return { damping: 14, stiffness: 160, mass: 0.55 };
    case "balanced":
    default:
      return { damping: 18, stiffness: 110, mass: 0.7 };
  }
};

/**
 * Map vibe.font_style to the Google Fonts family the scenes load. Each
 * scene file calls `loadFont()` on whatever this returns — the lazy import
 * lives at the call site so unused fonts don't bloat the bundle.
 */
export const fontFamilyFor = (
  style: VibeProfile["font_style"]
): "inter" | "manrope" | "spacegrotesk" | "ibmplexmono" => {
  switch (style) {
    case "editorial":
      return "manrope"; // closest available paid-news vibe in our font set
    case "kinetic-sans":
      return "spacegrotesk";
    case "mono-tech":
      return "ibmplexmono";
    case "neutral-sans":
    default:
      return "inter";
  }
};
