// Draws a circle annotation (like a marker pen circle) progressively around
// a target point. Uses @remotion/shapes to generate the path and
// @remotion/paths to animate it.

import React from "react";
import { interpolate, useCurrentFrame, Easing } from "remotion";
import { evolvePath } from "@remotion/paths";
import { makeCircle } from "@remotion/shapes";

interface DrawCircleProps {
  /** Center in canvas pixels */
  cx: number;
  cy: number;
  /** Radius in pixels */
  radius?: number;
  /** Start angle offset so drawing doesn't always begin at 3 o'clock (degrees) */
  startAngle?: number;
  color?: string;
  strokeWidth?: number;
  startFrame?: number;
  durationFrames?: number;
  canvasWidth?: number;
  canvasHeight?: number;
}

export const DrawCircle: React.FC<DrawCircleProps> = ({
  cx,
  cy,
  radius = 70,
  startAngle = -120,
  color = "#8B7FFF",
  strokeWidth = 7,
  startFrame = 0,
  durationFrames = 22,
  canvasWidth = 1080,
  canvasHeight = 1350,
}) => {
  const frame = useCurrentFrame();

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

  const { path } = makeCircle({ radius });
  const { strokeDasharray, strokeDashoffset } = evolvePath(progress, path);

  return (
    <svg
      width={canvasWidth}
      height={canvasHeight}
      style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "visible" }}
    >
      <g transform={`translate(${cx}, ${cy}) rotate(${startAngle})`}>
        <path
          d={path}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
};
