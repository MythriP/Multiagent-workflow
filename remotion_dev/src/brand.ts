// ─── BRAND CONFIG ────────────────────────────────────────────────────────────
// Single source of truth for all visual identity settings.
// Change ACCOUNT_NAME, ACCOUNT_HANDLE, and ACCENT_COLOR here
// and every template updates automatically.

export const BRAND = {
  // Account identity — swap these when you pick a name
  accountName: "PLACEHOLDER",
  accountHandle: "@placeholder",

  // Colors
  accent: "#00D4FF",              // cyan placeholder — swap to final accent color
  accentSecondary: "#8B7FFF",     // secondary accent (lavender) for variety
  background: "#0A0A0A",         // near-black (not pure #000)
  backgroundCard: "#111111",     // slightly lighter for card/embed backgrounds
  backgroundOverlay: "rgba(0,0,0,0.55)", // gradient overlay on hero images
  textPrimary: "#FFFFFF",
  textMuted: "rgba(255,255,255,0.60)",
  textDim: "rgba(255,255,255,0.35)",
  border: "rgba(255,255,255,0.10)",

  // Typography — IBM Plex Sans + IBM Plex Mono (same as startpinch.com)
  fontSans: "IBMPlexSans",
  fontMono: "IBMPlexMono",

  // ── Format dimensions ──────────────────────────────────────────────────
  // Primary: 9:16 vertical (Reels, TikTok, YT Shorts) — used by AnimatedVideo.
  // Slide: 4:5 portrait (IG carousels) — used by static slide templates.
  // Square: 1:1 (legacy IG feed).
  video: { width: 1080, height: 1920, fps: 30 },     // 9:16 vertical (PRIMARY)
  slide: { width: 1080, height: 1350, fps: 30 },     // 4:5 portrait (carousel)
  square: { width: 1080, height: 1080, fps: 30 },    // 1:1 (legacy)

  // Default to video dimensions — scenes inside AnimatedVideo reference these.
  // Static slide compositions explicitly pass BRAND.slide.width/height in Root.tsx.
  width: 1080,
  height: 1920,

  // Font sizes
  fontSize: {
    coverHeadline: 96,    // big bold hook text on cover (vertical → bigger)
    coverTagline: 30,     // small tagline below headline
    bodyText: 60,         // narrative text on body slides
    bodyTextLarge: 72,    // text-only body slides (more room)
    embedText: 52,        // context text above embed
    closerText: 60,       // closing statement text
    label: 26,            // monospace labels, slide numbers
    caption: 56,          // word-by-word voiceover captions (large for vertical)
  },

  // Spacing
  padding: {
    slide: 60,           // outer padding on all sides
    section: 40,         // between major sections
  },

  // Logo placeholder dimensions (top-left corner)
  logo: {
    size: 56,
  },

  // Caption renderer config (synced word highlights from ElevenLabs timestamps)
  caption: {
    bottomOffset: 280,   // px from bottom (above safe-zone for IG/TikTok captions UI)
    maxWordsPerLine: 4,  // wrap captions into short readable bursts
    paddingX: 60,
    paddingY: 14,
    backgroundColor: "rgba(0,0,0,0.78)",
    borderRadius: 12,
  },
} as const;
