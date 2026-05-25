import { AbsoluteFill, useCurrentFrame } from "remotion";

export const GrainOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const seed = (frame * 9301 + 49297) % 233280;
  const offsetX = (seed % 100) - 50;
  const offsetY = ((seed * 7) % 100) - 50;

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity: 0.08,
        mixBlendMode: "overlay",
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.6'/></svg>")`,
        backgroundSize: "300px 300px",
        backgroundPosition: `${offsetX}px ${offsetY}px`,
      }}
    />
  );
};
