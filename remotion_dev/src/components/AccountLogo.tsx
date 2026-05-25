import React from "react";
import { BRAND } from "../brand";

interface AccountLogoProps {
  size?: number;
  glowColor?: string;
}

// Placeholder logo — a simple geometric mark using the accent color.
// Replace the SVG inside with the real logo once the account is named.
export const AccountLogo: React.FC<AccountLogoProps> = ({
  size = BRAND.logo.size,
  glowColor = BRAND.accent,
}) => {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: `radial-gradient(circle at 35% 35%, ${glowColor}33, ${glowColor}11)`,
        border: `1.5px solid ${glowColor}55`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="4" fill={glowColor} />
        <circle cx="12" cy="12" r="9" stroke={glowColor} strokeWidth="1.5" opacity={0.5} />
      </svg>
    </div>
  );
};
