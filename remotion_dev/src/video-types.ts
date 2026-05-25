// ─── video-types.ts ──────────────────────────────────────────────────────────
// Zod schemas for video_script.json — the input format consumed by
// AnimatedVideo.tsx and scripts/render-video.ts.
//
// Each scene type maps directly to a scene component in src/scenes/.
// The top-level accent_color and audio_file are inherited by all scenes.

import { z } from "zod";
import { zColor } from "@remotion/zod-types";

// ─── Per-scene schemas ────────────────────────────────────────────────────────

export const hookSceneSchema = z.object({
  type: z.literal("hook"),
  duration_sec: z.number().min(1).default(5),
  headline: z.string(),
  accent_words: z.array(z.string()).default([]),
  bg_image: z.string().nullish(),
  tagline: z.string().nullish(),
});

export const contextSceneSchema = z.object({
  type: z.literal("context"),
  duration_sec: z.number().min(1).default(6),
  lines: z.array(z.string()),
  source_image: z.string().nullish(),
  source_label: z.string().nullish(),
  source_video: z.string().nullish(),
});

export const bodySceneSchema = z.object({
  type: z.literal("body"),
  duration_sec: z.number().min(1).default(8),
  lines: z.array(z.string()),
  image: z.string().nullish(),
  // Optional arrows: each entry is [x1,y1,x2,y2] in 0-1 fractions of slide dimensions
  arrows: z.array(z.tuple([z.number(), z.number(), z.number(), z.number()])).default([]),
});

export const paperSceneSchema = z.object({
  type: z.literal("paper"),
  duration_sec: z.number().min(1).default(10),
  paper_image: z.string(),
  title: z.string().nullish(),
  // Each entry: {label, cx, cy, radius} in pixels relative to 1080px wide image
  highlights: z
    .array(
      z.object({
        label: z.string(),
        cx: z.number(),
        cy: z.number(),
        radius: z.number().default(60),
      })
    )
    .default([]),
});

export const statSceneSchema = z.object({
  type: z.literal("stat"),
  duration_sec: z.number().min(1).default(4),
  number: z.number(),
  label: z.string(),
  prefix: z.string().default(""),
  suffix: z.string().default(""),
  context_line: z.string().nullish(),
});

export const quoteSceneSchema = z.object({
  type: z.literal("quote"),
  duration_sec: z.number().min(1).default(6),
  text: z.string(),
  speaker: z.string().nullish(),
  role: z.string().nullish(),
});

export const timelineSceneSchema = z.object({
  type: z.literal("timeline"),
  duration_sec: z.number().min(1).default(10),
  title: z.string().nullish(),
  events: z.array(
    z.object({
      date: z.string(),
      label: z.string(),
    })
  ),
});

export const compareSceneSchema = z.object({
  type: z.literal("compare"),
  duration_sec: z.number().min(1).default(8),
  left_label: z.string(),
  left_points: z.array(z.string()),
  right_label: z.string(),
  right_points: z.array(z.string()),
});

export const outroSceneSchema = z.object({
  type: z.literal("outro"),
  duration_sec: z.number().min(1).default(3),
  cta: z.string().default("Follow for more."),
  handle: z.string().nullish(),
});

// ─── New scene types — added for high-energy reactive content ────────────────

// BRollMontage: rapid-fire image cycling synced roughly to voiceover. Each
// image gets a subtle Ken Burns zoom and a quick mask transition between.
// Optional caption_lines render over the images on a per-image basis.
export const brollMontageSceneSchema = z.object({
  type: z.literal("broll_montage"),
  duration_sec: z.number().min(2).default(6),
  images: z.array(z.string()).min(1),
  // Optional one-line caption per image (rendered as a chip overlay)
  captions: z.array(z.string()).default([]),
  // Average frames per image (defaults to evenly split across duration)
  frames_per_image: z.number().int().min(15).nullish(),
  // Optional title chip pinned to the top throughout the montage
  title: z.string().nullish(),
});

// KineticType: word-by-word kinetic typography on solid background. Each
// word lands with a punchy spring + scale, optionally with selected words
// in accent color. Designed for hot-take "money lines" of voiceover.
export const kineticTypeSceneSchema = z.object({
  type: z.literal("kinetic_type"),
  duration_sec: z.number().min(1).default(4),
  text: z.string(),
  accent_words: z.array(z.string()).default([]),
  // Lines per group (default: 1 word per "burst", grouped by spaces)
  // If words_per_burst > 1, words land together as phrase chunks.
  words_per_burst: z.number().int().min(1).max(4).default(1),
  // Optional faint background image (Ken Burns) — usually omitted
  bg_image: z.string().nullish(),
});

// WebScroll: fakes scrolling through an article/web page screenshot,
// pausing to highlight a labelled region. Great for "here's the source"
// moments. Reuses DocumentScroll + DrawCircle internally (like PaperScene)
// but tuned for web articles instead of papers.
export const webScrollSceneSchema = z.object({
  type: z.literal("web_scroll"),
  duration_sec: z.number().min(3).default(7),
  screenshot: z.string(),
  source_label: z.string().nullish(),       // e.g. "techcrunch.com"
  // Pixel position to pause + highlight (relative to full screenshot height)
  highlight_y: z.number().nullish(),
  highlight_label: z.string().nullish(),
});

// ─── Discriminated union ──────────────────────────────────────────────────────

export const sceneSchema = z.discriminatedUnion("type", [
  hookSceneSchema,
  contextSceneSchema,
  bodySceneSchema,
  paperSceneSchema,
  statSceneSchema,
  quoteSceneSchema,
  timelineSceneSchema,
  compareSceneSchema,
  outroSceneSchema,
  brollMontageSceneSchema,
  kineticTypeSceneSchema,
  webScrollSceneSchema,
]);

export type Scene = z.infer<typeof sceneSchema>;
export type HookScene = z.infer<typeof hookSceneSchema>;
export type ContextScene = z.infer<typeof contextSceneSchema>;
export type BodyScene = z.infer<typeof bodySceneSchema>;
export type PaperScene = z.infer<typeof paperSceneSchema>;
export type StatScene = z.infer<typeof statSceneSchema>;
export type QuoteScene = z.infer<typeof quoteSceneSchema>;
export type TimelineScene = z.infer<typeof timelineSceneSchema>;
export type CompareScene = z.infer<typeof compareSceneSchema>;
export type OutroScene = z.infer<typeof outroSceneSchema>;
export type BRollMontageScene = z.infer<typeof brollMontageSceneSchema>;
export type KineticTypeScene = z.infer<typeof kineticTypeSceneSchema>;
export type WebScrollScene = z.infer<typeof webScrollSceneSchema>;

// ─── Word timestamp (from ElevenLabs) ────────────────────────────────────────

export const wordTimestampSchema = z.object({
  word: z.string(),
  start_sec: z.number(),
  end_sec: z.number(),
});
export type WordTimestamp = z.infer<typeof wordTimestampSchema>;

// ─── Top-level video script ───────────────────────────────────────────────────

export const videoScriptSchema = z.object({
  topic: z.string(),
  slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, {
    message: "slug must be lowercase kebab-case",
  }),
  accent_color: zColor().default("#8B7FFF"),
  audio_file: z.string().nullish(),
  word_timestamps: z.array(wordTimestampSchema).default([]),
  // When true (default), CaptionTrack overlays word-by-word captions across
  // every scene as long as word_timestamps is non-empty. Set false to hide.
  show_captions: z.boolean().default(true),
  scenes: z.array(sceneSchema).min(1),
});

export type VideoScript = z.infer<typeof videoScriptSchema>;

// ─── Props passed to every scene component (JSON scene + parent context) ─────

export interface SceneComponentProps {
  accentColor: string;
  durationFrames: number; // duration of THIS scene in frames
}
