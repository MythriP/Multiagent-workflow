// Dark overlay with a circular cutout that grows from a point.
// Use to draw attention to a specific area of an image or layout.
// Renders as an absolute-positioned SVG overlay.

import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { BRAND } from "../brand";

interface SpotlightProps {
  /** Center of the spotlight in canvas pixels */
  cx: number;
  cy: number;
  radius?: number;
  /** Opacity of the dark vignette surrounding the spotlight */
  vignetteOpacity?: number;
  startFrame?: number;
  durationFrames?: number;
}

export const Spotlight: React.FC<SpotlightProps> = ({
  cx,
  cy,
  radius = 130,
  vignetteOpacity = 0.82,
  startFrame = 0,
  durationFrames = 25,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const spotRadius =
    spring({
      frame: frame - startFrame,
      fps,
      config: { mass: 0.6, stiffness: 160, damping: 22 },
    }) * radius;

  const overlayOpacity = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, vignetteOpacity],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Use the brand width/height as canvas — the SVG fills the component's container
  const W = width || BRAND.width;
  const H = height || BRAND.height;

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <svg width={W} height={H}>
        <defs>
          <mask id={`spotlight-${cx}-${cy}`}>
            <rect width={W} height={H} fill="white" />
            <circle cx={cx} cy={cy} r={Math.max(0, spotRadius)} fill="black" />
          </mask>
        </defs>
        <rect
          width={W}
          height={H}
          fill="rgba(0,0,0,1)"
          opacity={overlayOpacity}
          mask={`url(#spotlight-${cx}-${cy})`}
        />
      </svg>
    </div>
  );
};
