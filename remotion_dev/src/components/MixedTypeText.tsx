import { loadFont as loadArchivoBlack } from "@remotion/google-fonts/ArchivoBlack";
import { loadFont as loadFraunces } from "@remotion/google-fonts/Fraunces";

const { fontFamily: archivoBlackFamily } = loadArchivoBlack();
const { fontFamily: frauncesFamily } = loadFraunces();

/** Public re-exports so other scenes can use the same Fraunces / Archivo
 *  Black families without each loading the font themselves. */
export const SERIF_ITALIC_FAMILY = frauncesFamily;
export const HEAVY_SANS_FAMILY = archivoBlackFamily;

type Props = {
  /** The full text to render. Spaces are preserved as word separators. */
  text: string;
  /** Words to render in italic Fraunces serif. Case-insensitive match
   *  against the punctuation-stripped lowercase token. The remaining words
   *  render in Archivo Black uppercase. */
  italicWords?: string[];
  /** Base font size in px. Italic words inherit the same size. */
  size?: number;
  /** Text color (applies to both runs). */
  color?: string;
  /** Optional accent color used only for italic words. Falls back to `color`. */
  italicColor?: string;
  /** Letter spacing for the heavy sans run. Default -2 (tight). */
  letterSpacing?: number;
  /** Line height. Default 1.05 (tight, headline-style). */
  lineHeight?: number;
  /** Horizontal text alignment. Default "center". */
  align?: "left" | "center" | "right";
  /** When true, the heavy sans run is uppercased (default). The italic run
   *  is always kept in its natural case to preserve the editorial feel. */
  uppercaseSans?: boolean;
  /** Optional inline style overrides applied to the wrapper. */
  style?: React.CSSProperties;
};

/**
 * MixedTypeText: renders a phrase as a mix of heavy bold sans (Archivo
 * Black) and italic serif (Fraunces). Mirrors the editorial-cinematic
 * typography pattern seen in the training reels (cf. exp1.mp4, exp4.mp4) —
 * one phrase, two voices, no glow, no gradients.
 *
 * Rules respected:
 *   • Flat — no textShadow, no boxShadow.
 *   • The italic accent words can use a separate color for emphasis.
 *   • Word-level spans, so spring/opacity timings can layer on top later.
 */
export const MixedTypeText: React.FC<Props> = ({
  text,
  italicWords = [],
  size = 110,
  color = "#ffffff",
  italicColor,
  letterSpacing = -2,
  lineHeight = 1.05,
  align = "center",
  uppercaseSans = true,
  style,
}) => {
  const italicSet = new Set(
    italicWords
      .map((w) => w.toLowerCase().replace(/[^a-z0-9]/g, ""))
      .filter(Boolean)
  );
  const tokens = text.split(/(\s+)/);

  return (
    <div
      style={{
        fontSize: size,
        lineHeight,
        textAlign: align,
        color,
        ...style,
      }}
    >
      {tokens.map((tok, i) => {
        if (/^\s+$/.test(tok)) {
          return <span key={i}>{tok}</span>;
        }
        const normalized = tok.toLowerCase().replace(/[^a-z0-9]/g, "");
        const isItalic = italicSet.has(normalized);
        if (isItalic) {
          return (
            <span
              key={i}
              style={{
                fontFamily: frauncesFamily,
                fontWeight: 400,
                fontStyle: "italic",
                color: italicColor ?? color,
                letterSpacing: 0,
              }}
            >
              {tok}
            </span>
          );
        }
        return (
          <span
            key={i}
            style={{
              fontFamily: archivoBlackFamily,
              fontWeight: 900,
              letterSpacing,
              textTransform: uppercaseSans ? "uppercase" : undefined,
            }}
          >
            {tok}
          </span>
        );
      })}
    </div>
  );
};
