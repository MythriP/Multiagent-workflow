// Draws an SVG path progressively — mimics a hand-drawn arrow or annotation.
// Accepts a raw SVG path string (`d` attribute) or two (x1,y1)→(x2,y2) points.
// When using points, a natural-looking quadratic bezier curve is generated.

import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";
import { evolvePath } from "@remotion/paths";

interface DrawArrowProps {
  /** Full SVG path string (d attribute). Overrides x1/y1/x2/y2 if provided. */
  path?: string;
  /** Convenience: start point in canvas pixels */
  x1?: number;
  y1?: number;
  /** Convenience: end point in canvas pixels */
  x2?: number;
  y2?: number;
  /** How much the bezier arc bows perpendicular to the straight line (px) */
  bow?: number;
  color?: string;
  strokeWidth?: number;
  startFrame?: number;
  durationFrames?: number;
  /** Draw an arrowhead at the end */
  arrowhead?: boolean;
  canvasWidth?: number;
  canvasHeight?: number;
}

function makeCurvedPath(
  x1: number, y1: number,
  x2: number, y2: number,
  bow: number
): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2 - bow;
  return `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
}

export const DrawArrow: React.FC<DrawArrowProps> = ({
  path,
  x1 = 100, y1 = 100,
  x2 = 300, y2 = 300,
  bow = 60,
  color = "#FFFFFF",
  strokeWidth = 6,
  startFrame = 0,
  durationFrames = 25,
  arrowhead = true,
  canvasWidth = 1080,
  canvasHeight = 1350,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // fps kept to satisfy no-unused-locals via a comment; used for future spring
  void fps;

  const resolvedPath = path ?? makeCurvedPath(x1, y1, x2, y2, bow);

  const progress = interpolate(
    frame,
    [startFrame, startFrame + durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  const { strokeDasharray, strokeDashoffset } = evolvePath(progress, resolvedPath);

  // Arrowhead: a small triangle at the end tip
  const endX = path ? x2 : x2;
  const endY = path ? y2 : y2;
  const arrowOpacity = interpolate(progress, [0.85, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg
      width={canvasWidth}
      height={canvasHeight}
      style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "visible" }}
    >
      <path
        d={resolvedPath}
        stroke={color}
        strokeWidth={strokeWidth}
        fill="none"
        strokeDasharray={strokeDasharray}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {arrowhead && (
        <polygon
          points={`
            ${endX},${endY}
            ${endX - 12},${endY - 20}
            ${endX + 12},${endY - 20}
          `}
          fill={color}
          opacity={arrowOpacity}
        />
      )}
    </svg>
  );
};
