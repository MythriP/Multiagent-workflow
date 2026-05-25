// ─── post.json schema ────────────────────────────────────────────────────────
// The shape of input files the render-post script consumes.
// In Phase 2 you write these manually. In Phase 3, an AI script generator
// will produce these files automatically from a topic.

import { z } from "zod";

import { coverSlideSchema } from "../src/templates/CoverSlide/CoverSlide";
import { bodySlideSchema } from "../src/templates/BodySlide/BodySlide";
import { embedSlideSchema } from "../src/templates/EmbedSlide/EmbedSlide";
import { closerSlideSchema } from "../src/templates/CloserSlide/CloserSlide";

// A single slide entry — discriminated union by `type`
export const slideEntrySchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("cover"), props: coverSlideSchema }),
  z.object({ type: z.literal("body"), props: bodySlideSchema }),
  z.object({ type: z.literal("embed"), props: embedSlideSchema }),
  z.object({ type: z.literal("closer"), props: closerSlideSchema }),
]);

export type SlideEntry = z.infer<typeof slideEntrySchema>;

// The full post object — what lives in post.json
export const postJsonSchema = z.object({
  // Human-readable topic name (for logs and metadata)
  topic: z.string(),
  // 1-2 keyword folder slug, kebab-case (e.g. "anthropic-mythos")
  slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, {
    message: "slug must be lowercase, kebab-case (e.g. 'anthropic-mythos')",
  }),
  // Ordered list of slides
  slides: z.array(slideEntrySchema).min(1),
  // Long-form caption to copy into the IG post body
  caption: z.string(),
  // Hashtags (with or without # — both accepted)
  hashtags: z.array(z.string()).default([]),
});

export type PostJson = z.infer<typeof postJsonSchema>;

// Maps slide type → Composition ID registered in Root.tsx
export const COMPOSITION_ID_BY_TYPE: Record<SlideEntry["type"], string> = {
  cover: "CoverSlide",
  body: "BodySlideWithImage", // BodySlide handles both modes via hasImage
  embed: "EmbedSlide",
  closer: "CloserSlide",
};
