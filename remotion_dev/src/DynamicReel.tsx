import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  Series,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";
import { zColor } from "@remotion/zod-types";

import { HookCard } from "./scenes/HookCard";
import { ReactiveCreatorHook } from "./scenes/ReactiveCreatorHook";
import { ChatScene } from "./scenes/ChatScene";
import { CtaCard } from "./scenes/CtaCard";
import { PaperScrollScene } from "./scenes/PaperScrollScene";
import { PaperWalkthroughScene } from "./scenes/PaperWalkthroughScene";
import { BarChartScene } from "./scenes/article2/BarChartScene";
import { ComparisonScene } from "./scenes/article2/ComparisonScene";
import { QuoteCard } from "./scenes/article2/QuoteCard";
import { HeadlineCard } from "./scenes/article2/HeadlineCard";
import { SplitScreenScene } from "./scenes/SplitScreenScene";
import { PipelineHighlightScene } from "./scenes/PipelineHighlightScene";
import { FloatingWindowScene } from "./scenes/FloatingWindowScene";
import { NumberedRevealScene } from "./scenes/NumberedRevealScene";
import { ArticleHeadlineScene } from "./scenes/ArticleHeadlineScene";
// AvatarOverlay is no longer mounted (the global floating-bust system was
// removed when the hook + avatar_full scenes took over avatar duties), but
// the file remains in /components for back-compat with any external import.
import { DramaticWord } from "./components/DramaticWord";
import { GrainOverlay } from "./components/GrainOverlay";
import { VignetteOverlay } from "./components/VignetteOverlay";
import { PillCaption, type PillWord } from "./components/PillCaption";
import {
  StatementOverlay,
  type StatementSegment,
} from "./components/StatementOverlay";

// ─── Per-scene Zod schemas ────────────────────────────────────────────────────

const wordTimestampSchema = z.object({
  text: z.string(),
  start: z.number(),
  end: z.number(),
  line: z.number().optional(),
});

const baseSceneSchema = z.object({
  duration_sec: z.number().min(0.5).max(20),
  /** Per-scene avatar visibility flag computed by script_agent. The scene
   *  builder uses image aspect ratio + scene type + ≥3s gating to decide.
   *  Falls back to the type-based heuristic when null/undefined. */
  host_avatar: z.boolean().nullish(),
  /** Phase C lipsync (Option B). When set, the scene plays this mp4
   *  instead of the still avatar. The clip is generated from
   *  avatar-source.png by lipsync.py and staged at the given
   *  staticFile-relative path. Only HookCard and AvatarFullScene
   *  currently consume it. */
  lipsync_clip_src: z.string().nullish(),
  /** Offset in seconds into `lipsync_clip_src` where THIS scene starts.
   *  When the avatar segment spans multiple scenes, all of them share
   *  one mp4 — the offset trims the playhead to the correct sub-window. */
  lipsync_clip_start_sec: z.number().nullish(),
});

export const hookSceneSchema = baseSceneSchema.extend({
  type: z.literal("hook"),
  hook: z.string(),
  subtitle: z.string().default(""),
  /** Optional ambient blurred back layer (Pexels video preferred). */
  bg_media_src: z.string().nullish(),
});

// ─── New 5-pattern scene catalog ────────────────────────────────────────────
// All five share the same family of fields so the scene_writer can choose
// patterns without rewriting source material. Motion is "lock into place"
// (slides in from a direction, then holds). No focal stops, no zoom pulses.

const slideFromValues = ["top", "bottom", "left", "right"] as const;

const mediaPaneSchema = z.object({
  /** "text" pane shows the article excerpt / headline as text. "media" pane
   *  shows an image or video. Never use text+text in a split — see
   *  splitScreenSceneSchema. */
  kind: z.enum(["text", "media"]),
  /** Used when kind === "text". 1–3 short lines. */
  text: z.string().nullish(),
  /** Used when kind === "media". Local path or staticFile-relative path. */
  src: z.string().nullish(),
  /** Tiny chip (e.g. source domain) shown in a corner of this pane. */
  source_label: z.string().nullish(),
  /** Direction this pane enters from. Must oppose the other pane. */
  slide_from: z.enum(slideFromValues).default("top"),
  /** Optional list of words inside `text` that should render in italic
   *  Fraunces serif instead of the default Archivo Black sans. Used by
   *  <MixedTypeText> on text panes. Case-insensitive; punctuation
   *  stripped before matching. Ignored for media panes. */
  accent_italic_words: z.array(z.string()).nullish(),
});

export const splitScreenSceneSchema = baseSceneSchema.extend({
  type: z.literal("split_screen"),
  /** Phase B locks this to "horizontal" only. The schema still accepts
   *  "vertical" so old scripts deserialise, but Python coerces vertical
   *  to horizontal before the scene reaches the renderer, and the
   *  renderer treats anything other than "horizontal" as horizontal. */
  orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
  /** Top pane. */
  pane_a: mediaPaneSchema,
  /** Bottom pane. */
  pane_b: mediaPaneSchema,
  /** Phase B retired the scene-level keyword pill. The field is kept on
   *  the schema for back-compat with older scripts; the renderer
   *  ignores it. */
  keyword: z.string().nullish(),
});

export const pipelineHighlightSceneSchema = baseSceneSchema.extend({
  type: z.literal("pipeline_highlight"),
  /** The full diagram / pipeline screenshot. */
  diagram_src: z.string(),
  /** Phase B retired the bbox highlight system (the LLM hallucinated
   *  coordinates because it never saw the diagram, so highlights landed
   *  in empty regions). Field is kept on the schema for back-compat
   *  with old scripts; the renderer no longer uses it. */
  highlights: z
    .array(
      z.object({
        x: z.number().min(0).max(1),
        y: z.number().min(0).max(1),
        w: z.number().min(0).max(1),
        h: z.number().min(0).max(1),
        label: z.string().default(""),
        dwell_sec: z.number().min(0.4).max(8).nullish(),
      })
    )
    .nullish(),
  /** Optional path to a Veo-generated animation of the same diagram — if
   *  present, the renderer plays it instead of the static diagram. */
  animated_src: z.string().nullish(),
  source: z.string().nullish(),
  /** Editorial bold caption rendered in the empty strip above the diagram.
   *  2–5 words, used as a top label. Phase B replacement for bbox labels. */
  top_annotation: z.string().nullish(),
  /** Editorial bold caption rendered in the empty strip below the diagram. */
  bottom_annotation: z.string().nullish(),
});

export const floatingWindowSceneSchema = baseSceneSchema.extend({
  type: z.literal("floating_window"),
  /** The content inside the floating frame. Image, video, map, or UI shot. */
  window_src: z.string(),
  /** Legacy single-keyword pill. Phase B retired this; the renderer ignores
   *  the field but it stays on the schema for back-compat with older
   *  scripts. */
  keyword: z.string().default(""),
  /** Aspect of the floating window. Default 16:9. */
  window_aspect: z.enum(["16:9", "4:3", "1:1", "9:16"]).default("16:9"),
  /** Tiny source chip in the corner of the floating window. */
  source_label: z.string().nullish(),
  /** For video window_src only — start offset in seconds. */
  video_start_sec: z.number().min(0).max(600).nullish(),
});

export const numberedRevealSceneSchema = baseSceneSchema.extend({
  type: z.literal("numbered_reveal"),
  /** Circle number. Defaults to 1; Python auto-renumbers all
   *  numbered_reveal scenes 1..N in render order so the LLM doesn't
   *  have to (and can't accidentally double up "3" twice). */
  number: z.number().int().min(1).max(99).default(1),
  /** Bold title text rendered to the right of the circle (hard cap 22
   *  chars enforced upstream in Python). */
  title: z.string(),
  /** Optional supporting content shown below the circle+title row. */
  window_src: z.string().nullish(),
  /** Legacy keyword pill. Retired in Phase B; renderer ignores. */
  keyword: z.string().default(""),
  /** For video window_src only. */
  video_start_sec: z.number().min(0).max(600).nullish(),
});

export const articleHeadlineSceneSchema = baseSceneSchema.extend({
  type: z.literal("article_headline"),
  /** The article screenshot / headline image. */
  article_src: z.string(),
  /** Phrase inside the article to wrap with a colored selection box. */
  highlight_phrase: z.string().default(""),
  /** Bbox of that phrase in image-space (0..1). When provided, the renderer
   *  uses it directly; otherwise it falls back to a centered placeholder
   *  highlight near the top of the screenshot. */
  highlight_bbox: z
    .object({
      x: z.number().min(0).max(1),
      y: z.number().min(0).max(1),
      w: z.number().min(0).max(1),
      h: z.number().min(0).max(1),
    })
    .nullish(),
  /** The emotional / contextual photo shown below the article. */
  emotional_src: z.string().nullish(),
  /** Word callout that pops onto the emotional photo at duration_sec/2. */
  word_callout: z.string().default(""),
  source_label: z.string().nullish(),
});

export const paperScrollSceneSchema = baseSceneSchema.extend({
  type: z.literal("paper_scroll"),
  imageSrc: z.string(),
  caption: z.string().default(""),
  source: z.string().nullish(),
});

export const paperWalkthroughStopSchema = z.object({
  scrollY: z.number(),
  highlight: z
    .object({
      x: z.number(),
      y: z.number(),
      w: z.number(),
      h: z.number(),
    })
    .nullish(),
  caption: z.string().default(""),
  dwell_sec: z.number().min(0.5).max(20).default(3),
});

export const paperWalkthroughSceneSchema = z
  .object({
    type: z.literal("paper_walkthrough"),
    /** Total scene duration. The renderer ALSO trusts the sum of stop dwells
     * + transitions, but we still require this for schema consistency. */
    duration_sec: z.number().min(1).max(120),
    imageSrc: z.string(),
    stops: z.array(paperWalkthroughStopSchema).min(1).max(12),
    source: z.string().nullish(),
    transition_frames: z.number().min(0).max(120).default(24),
    host_avatar: z.boolean().nullish(),
  });

export const headlineSceneSchema = baseSceneSchema.extend({
  type: z.literal("headline"),
  kicker: z.string().default(""),
  headline: z.string(),
  subhead: z.string().nullish(),
  source: z.string().nullish(),
  /** Optional supporting image, rendered behind a dark scrim. */
  bg_image: z.string().nullish(),
  /** Optional ambient blurred back layer (Pexels video / image). */
  bg_media_src: z.string().nullish(),
});

export const barChartSceneSchema = baseSceneSchema.extend({
  type: z.literal("bar_chart"),
  title: z.string(),
  subtitle: z.string().nullish(),
  yAxisLabel: z.string().nullish(),
  bars: z
    .array(
      z.object({
        label: z.string(),
        value: z.number(),
        formatted: z.string(),
        color: z.string().default("#999"),
        highlight: z.boolean().nullish(),
      })
    )
    .min(2),
});

export const comparisonSceneSchema = baseSceneSchema.extend({
  type: z.literal("comparison"),
  title: z.string(),
  left: z.object({
    brand: z.string(),
    brandColor: z.string().default("#10A37F"),
    emoji: z.string().default(""),
    value: z.string(),
    unit: z.string().default(""),
  }),
  right: z.object({
    brand: z.string(),
    brandColor: z.string().default("#4285F4"),
    emoji: z.string().default(""),
    value: z.string(),
    unit: z.string().default(""),
  }),
  multiplier: z
    .object({
      number: z.string(),
      label: z.string(),
      color: z.string().default("#10A37F"),
    })
    .nullish(),
});

export const quoteSceneSchema = baseSceneSchema.extend({
  type: z.literal("quote"),
  text: z.string(),
  highlight: z.array(z.string()).default([]),
  background: z.string().default("white"),
  bg_media_src: z.string().nullish(),
});

export const dramaticWordSceneSchema = baseSceneSchema.extend({
  type: z.literal("dramatic_word"),
  text: z.string(),
  variant: z.enum(["italic-serif", "bold-sans"]).default("italic-serif"),
  background: z.string().default("#0a0a0a"),
  textColor: z.string().default("#ffffff"),
  /** Optional ambient blurred back layer (Pexels video preferred). When set,
   *  it replaces the solid `background` color. */
  bg_media_src: z.string().nullish(),
});

export const chatTurnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  text: z.string(),
  thinking: z.string().nullish(),
});

export const chatSceneSchema = z.object({
  type: z.literal("chat"),
  /** Total scene duration. Should be ≥ computeChatSceneDuration(turns) so
   *  nothing gets cut mid-stream. The script agent fills this automatically. */
  duration_sec: z.number().min(1).max(120),
  /** Which app skin to render. Defaults to "claude". */
  app: z.enum(["claude", "chatgpt", "gemini"]).default("claude"),
  /** Footer label such as "Sonnet 4.5  Extended". Optional — has per-app default. */
  model_label: z.string().nullish(),
  /** Conversation, in order. Should alternate user/assistant. */
  turns: z.array(chatTurnSchema).min(1).max(8),
  host_avatar: z.boolean().nullish(),
  /** Optional ambient backdrop (typically a Pexels b-roll clip).
   *  Renders blurred under the desktop chat window. The script agent
   *  auto-fills this for chat scenes when none is provided. */
  bg_media_src: z.string().nullish(),
});

export const ctaSceneSchema = baseSceneSchema.extend({
  type: z.literal("cta"),
  text: z.string(),
  /** Optional ambient blurred back layer. The CTA is plain black by default
   *  so the avatar is the visual hero; only set this if you really want
   *  motion behind the bust. */
  bg_media_src: z.string().nullish(),
});

// ─── Vibe profile (visual aesthetic decided by vibe_planner.py) ─────────────

export const vibeProfileSchema = z.object({
  vibe_name: z.string().default("clean_tech_serious"),
  tone_summary: z.string().default(""),
  color_palette: z.object({
    primary_bg: z.string().default("#0A0A0A"),
    secondary_bg: z.string().default("#141414"),
    accent: z.string().default("#8B7FFF"),
    text_primary: z.string().default("#FFFFFF"),
  }),
  motion_intensity: z.enum(["calm", "balanced", "kinetic"]).default("balanced"),
  font_style: z
    .enum(["editorial", "neutral-sans", "kinetic-sans", "mono-tech"])
    .default("editorial"),
  /** Phase B: hook scene 0 layout. "split_50_50" = HookCard
   *  (title pane + avatar). "reactive_creator" = full-canvas Veo
   *  cinematic clip + minimal subtitle pill. Vibe-determined. */
  hook_variant: z
    .enum(["split_50_50", "reactive_creator"])
    .default("split_50_50"),
  /** Phase B: only one vibe in the catalog (bold_statement) allows
   *  the dramatic_word scene type. Python coerces extra ones out. */
  allow_dramatic_word: z.boolean().default(false),
  /** Phase B: whether VibeBackdrop renders the editorial dot grid. */
  dot_grid_enabled: z.boolean().default(true),
  /** Phase C: default anchor for the StatementOverlay. Per-scene
   *  overrides (avatar visible → top_right, top-heavy hero →
   *  bottom_left) apply on top of this. */
  statement_anchor: z
    .enum(["top_right", "bottom_left"])
    .default("bottom_left"),
  video_gen_modifiers: z.array(z.string()).default([]),
  scene_pattern_bias: z
    .object({
      split_screen: z.number().default(0.7),
      pipeline_highlight: z.number().default(0.5),
      floating_window: z.number().default(0.5),
      numbered_reveal: z.number().default(0.4),
      article_headline: z.number().default(0.5),
    })
    .default(() => ({
      split_screen: 0.7,
      pipeline_highlight: 0.5,
      floating_window: 0.5,
      numbered_reveal: 0.4,
      article_headline: 0.5,
    })),
  ambient_backdrop_queries: z.array(z.string()).default([]),
});

export type VibeProfile = z.infer<typeof vibeProfileSchema>;

const DEFAULT_VIBE: VibeProfile = {
  vibe_name: "clean_tech_serious",
  tone_summary: "",
  color_palette: {
    primary_bg: "#0A0A0A",
    secondary_bg: "#141414",
    accent: "#8B7FFF",
    text_primary: "#FFFFFF",
  },
  motion_intensity: "balanced",
  font_style: "editorial",
  hook_variant: "split_50_50",
  allow_dramatic_word: false,
  dot_grid_enabled: true,
  statement_anchor: "bottom_left",
  video_gen_modifiers: [],
  scene_pattern_bias: {
    split_screen: 0.7,
    pipeline_highlight: 0.5,
    floating_window: 0.5,
    numbered_reveal: 0.4,
    article_headline: 0.5,
  },
  ambient_backdrop_queries: [],
};

// Avatar full-canvas slot — inserted by the Python pipeline at the two
// mid-reel positions. Replaces the legacy AvatarOverlay system. Renders the
// avatar environment photo full-bleed, no other content, captions still
// ride on top via the global PillCaption.
export const avatarFullSceneSchema = baseSceneSchema.extend({
  type: z.literal("avatar_full"),
  duration_sec: z.number().min(1).max(8).default(4),
  /** Optional path override. Defaults to /avatar/avatar-source.png in public/. */
  imageSrc: z.string().nullish(),
});

export const sceneSchema = z.discriminatedUnion("type", [
  hookSceneSchema,
  splitScreenSceneSchema,
  pipelineHighlightSceneSchema,
  floatingWindowSceneSchema,
  numberedRevealSceneSchema,
  articleHeadlineSceneSchema,
  paperScrollSceneSchema,
  paperWalkthroughSceneSchema,
  headlineSceneSchema,
  barChartSceneSchema,
  comparisonSceneSchema,
  quoteSceneSchema,
  dramaticWordSceneSchema,
  chatSceneSchema,
  ctaSceneSchema,
  avatarFullSceneSchema,
]);

export type Scene = z.infer<typeof sceneSchema>;

// ─── Top-level Reel schema ────────────────────────────────────────────────────

export const dynamicReelSchema = z.object({
  topic: z.string(),
  slug: z.string(),
  accent_color: zColor().default("#FF3D71"),
  /** File name relative to public/voiceovers/ — e.g. "voiceovers/<slug>.mp3" */
  audio_file: z.string().nullish(),
  /** Word-level timestamps consumed by the bottom PillCaption overlay */
  word_timestamps: z.array(wordTimestampSchema).default([]),
  /** Words that should pop in accent-yellow when spoken */
  accent_words: z.array(z.string()).default([]),
  scenes: z.array(sceneSchema).min(1),
  /** Toggle global grain + vignette overlays. Default true. */
  show_overlays: z.boolean().default(true),
  /**
   * Path to a headshot under `public/` (e.g. "avatar/headshot.png"). When
   * present, AvatarOverlay renders the bust at bottom-center on scenes in
   * NARRATOR_ON_CAMERA_TYPES. Set to null to disable the avatar entirely.
   */
  avatar_image: z.string().nullish(),
  /** Optional fal.ai/VEED lip-sync video that replaces the still bust. */
  avatar_video: z.string().nullish(),
  /** Visual vibe profile produced by vibe_planner.py. Drives color palette,
   *  motion intensity, and font mood across every scene. Optional — falls
   *  back to clean-tech-serious defaults when absent. */
  vibe: vibeProfileSchema.nullish(),
  /** Phase C statement-mode timeline: whole-phrase callouts that take
   *  over from the per-word PillCaption for declarative beats. Anchored
   *  top-right or bottom-left per the Python pipeline's decision. */
  statement_segments: z
    .array(
      z.object({
        text: z.string(),
        start: z.number(),
        end: z.number(),
        anchor: z.enum(["top_right", "bottom_left"]).default("bottom_left"),
        italic_words: z.array(z.string()).nullish(),
      })
    )
    .default([]),
  /** Phase D SFX layer: short UI / atmospheric cues placed on the
   *  reel timeline. Each cue points at a public/sfx/<file>.wav,
   *  mounted via a Sequence-windowed <Audio>. */
  sfx_track: z
    .array(
      z.object({
        intent: z.string().optional(),
        src: z.string(),
        start_sec: z.number(),
        duration_sec: z.number(),
        volume: z.number().min(0).max(1).default(0.4),
      })
    )
    .default([]),
});

export type DynamicReelProps = z.infer<typeof dynamicReelSchema>;

// ─── calculateMetadata: total frames = sum(scene durations) at 30fps ─────────

export const calculateMetadata = ({ props }: { props: DynamicReelProps }) => {
  const fps = 30;
  const totalSec = props.scenes.reduce((s, sc) => s + sc.duration_sec, 0);
  return {
    durationInFrames: Math.max(1, Math.round(totalSec * fps)),
    fps,
  };
};

// ─── Scene dispatcher ────────────────────────────────────────────────────────

function renderScene(
  scene: Scene,
  accentColor: string,
  index: number,
  vibe: VibeProfile
): React.ReactNode {
  switch (scene.type) {
    case "hook":
      // Phase B: vibe.hook_variant decides which hook component renders.
      //   split_50_50      → HookCard (title pane top, avatar bottom)
      //   reactive_creator → ReactiveCreatorHook (full-canvas bg + title)
      return vibe.hook_variant === "reactive_creator" ? (
        <ReactiveCreatorHook
          hook={scene.hook}
          subtitle={scene.subtitle}
          accentColor={accentColor}
          bgMediaSrc={scene.bg_media_src ?? undefined}
          vibe={vibe}
        />
      ) : (
        <HookCard
          hook={scene.hook}
          subtitle={scene.subtitle}
          accentColor={accentColor}
          bgMediaSrc={scene.bg_media_src ?? undefined}
          vibe={vibe}
          lipsyncClipSrc={scene.lipsync_clip_src ?? undefined}
          lipsyncClipStartSec={scene.lipsync_clip_start_sec ?? undefined}
        />
      );
    case "split_screen":
      return (
        <SplitScreenScene
          orientation="horizontal"
          paneA={scene.pane_a}
          paneB={scene.pane_b}
          accentColor={accentColor}
          vibe={vibe}
        />
      );
    case "pipeline_highlight":
      return (
        <PipelineHighlightScene
          diagramSrc={scene.diagram_src}
          animatedSrc={scene.animated_src ?? undefined}
          source={scene.source ?? undefined}
          topAnnotation={scene.top_annotation ?? undefined}
          bottomAnnotation={scene.bottom_annotation ?? undefined}
          accentColor={accentColor}
          vibe={vibe}
        />
      );
    case "floating_window":
      return (
        <FloatingWindowScene
          windowSrc={scene.window_src}
          windowAspect={scene.window_aspect}
          sourceLabel={scene.source_label ?? undefined}
          videoStartSec={scene.video_start_sec ?? undefined}
          accentColor={accentColor}
          vibe={vibe}
        />
      );
    case "numbered_reveal":
      return (
        <NumberedRevealScene
          number={scene.number}
          title={scene.title}
          windowSrc={scene.window_src ?? undefined}
          videoStartSec={scene.video_start_sec ?? undefined}
          accentColor={accentColor}
          vibe={vibe}
        />
      );
    case "article_headline":
      return (
        <ArticleHeadlineScene
          articleSrc={scene.article_src}
          highlightPhrase={scene.highlight_phrase}
          highlightBbox={scene.highlight_bbox ?? undefined}
          emotionalSrc={scene.emotional_src ?? undefined}
          wordCallout={scene.word_callout}
          sourceLabel={scene.source_label ?? undefined}
          accentColor={accentColor}
          vibe={vibe}
        />
      );
    case "paper_scroll":
      return (
        <PaperScrollScene
          imageSrc={scene.imageSrc}
          caption={scene.caption}
          source={scene.source ?? undefined}
          accentColor={accentColor}
        />
      );
    case "paper_walkthrough":
      return (
        <PaperWalkthroughScene
          imageSrc={scene.imageSrc}
          stops={scene.stops.map((s) => ({
            scrollY: s.scrollY,
            caption: s.caption,
            dwell_sec: s.dwell_sec,
          }))}
          source={scene.source ?? undefined}
          accentColor={accentColor}
          transitionFrames={scene.transition_frames}
        />
      );
    case "headline":
      return (
        <HeadlineCard
          kicker={scene.kicker}
          headline={scene.headline}
          subhead={scene.subhead ?? undefined}
          source={scene.source ?? undefined}
          accentColor={accentColor}
          bgImage={scene.bg_image ?? undefined}
          bgMediaSrc={scene.bg_media_src ?? undefined}
          vibe={vibe}
        />
      );
    case "bar_chart":
      return (
        <BarChartScene
          title={scene.title}
          subtitle={scene.subtitle ?? undefined}
          yAxisLabel={scene.yAxisLabel ?? undefined}
          bars={scene.bars.map((b) => ({
            label: b.label,
            value: b.value,
            formatted: b.formatted,
            color: b.color,
            highlight: b.highlight ?? false,
          }))}
          accentColor={accentColor}
        />
      );
    case "comparison":
      return (
        <ComparisonScene
          title={scene.title}
          left={scene.left}
          right={scene.right}
          multiplier={scene.multiplier ?? undefined}
        />
      );
    case "quote":
      return (
        <QuoteCard
          text={scene.text}
          highlight={scene.highlight}
          accentColor={accentColor}
          background={scene.background}
          bgMediaSrc={scene.bg_media_src ?? undefined}
        />
      );
    case "dramatic_word":
      return (
        <DramaticWord
          text={scene.text}
          variant={scene.variant}
          background={scene.background}
          textColor={scene.textColor}
          bgMediaSrc={scene.bg_media_src ?? undefined}
          vibe={vibe}
        />
      );
    case "chat":
      return (
        <ChatScene
          app={scene.app}
          turns={scene.turns.map((t) => ({
            role: t.role,
            text: t.text,
            thinking: t.thinking ?? undefined,
          }))}
          modelLabel={scene.model_label ?? undefined}
          accentColor={accentColor}
          bgMediaSrc={scene.bg_media_src ?? undefined}
        />
      );
    case "cta":
      return (
        <CtaCard
          text={scene.text}
          accentColor={accentColor}
          bgMediaSrc={scene.bg_media_src ?? undefined}
          vibe={vibe}
        />
      );
    case "avatar_full":
      return (
        <AvatarFullScene
          imageSrc={scene.imageSrc ?? undefined}
          lipsyncClipSrc={scene.lipsync_clip_src ?? undefined}
          lipsyncClipStartSec={scene.lipsync_clip_start_sec ?? undefined}
        />
      );
  }
}

// ─── AvatarFullScene ─────────────────────────────────────────────────────────
// Full-canvas avatar environment photo. Inserted by the Python pipeline at
// the two mid-reel positions. The hook scene handles its own avatar via
// HookCard's 50/50 layout, so this component covers ONLY the mid-reel slots.

const AvatarFullScene: React.FC<{
  imageSrc?: string;
  lipsyncClipSrc?: string;
  lipsyncClipStartSec?: number;
}> = ({ imageSrc, lipsyncClipSrc, lipsyncClipStartSec }) => {
  const { fps } = useVideoConfig();
  if (lipsyncClipSrc) {
    const startFrom = lipsyncClipStartSec
      ? Math.round(lipsyncClipStartSec * fps)
      : undefined;
    return (
      <AbsoluteFill style={{ backgroundColor: "#000" }}>
        <OffthreadVideo
          src={staticFile(lipsyncClipSrc)}
          muted
          startFrom={startFrom}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center center",
          }}
        />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Img
        src={staticFile(imageSrc ?? "avatar/avatar-source.png")}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center center",
        }}
      />
    </AbsoluteFill>
  );
};

// ─── Component ───────────────────────────────────────────────────────────────

export const DynamicReel: React.FC<DynamicReelProps> = ({
  accent_color,
  audio_file,
  word_timestamps,
  accent_words,
  scenes,
  show_overlays,
  avatar_image,
  avatar_video,
  vibe,
  statement_segments,
  sfx_track,
}) => {
  const { fps } = useVideoConfig();
  const resolvedVibe: VibeProfile = vibe ?? DEFAULT_VIBE;
  // When a vibe is present its accent color wins over the per-reel accent
  // unless the per-reel value was explicitly customized. The script_agent
  // syncs both fields so this is rarely user-visible.
  const effectiveAccent = vibe?.color_palette.accent ?? accent_color;

  // Compute each scene's [start..end] in seconds so we can tag every word
  // with the scene's layout flags (e.g. splitSeam for 50/50 scenes — the
  // hook and any `split_screen`). PillCaption uses this to know whether to
  // ride the seam (y=960) or bottom-anchor.
  const sceneBoundaries: Array<{
    start: number;
    end: number;
    splitSeam: boolean;
  }> = (() => {
    const out: Array<{ start: number; end: number; splitSeam: boolean }> = [];
    let cursor = 0;
    for (const s of scenes) {
      const start = cursor;
      const end = cursor + s.duration_sec;
      const splitSeam = s.type === "hook" || s.type === "split_screen";
      out.push({ start, end, splitSeam });
      cursor = end;
    }
    return out;
  })();

  const findSceneFlags = (t: number): { splitSeam: boolean } => {
    for (const sb of sceneBoundaries) {
      if (t >= sb.start && t < sb.end) return { splitSeam: sb.splitSeam };
    }
    return { splitSeam: false };
  };

  // Phase C: a word falls inside a statement-mode window if any segment's
  // [start..end] contains the word's mid-point. Suppressed words still
  // pass through to PillCaption — the component skips rendering them.
  const isInsideStatementWindow = (t: number): boolean => {
    for (const seg of statement_segments) {
      if (t >= seg.start && t < seg.end) return true;
    }
    return false;
  };

  const pillWords: PillWord[] = word_timestamps.map((w) => {
    const mid = (w.start + w.end) / 2;
    return {
      text: w.text,
      start: w.start,
      end: w.end,
      line: w.line,
      splitSeam: findSceneFlags(mid).splitSeam,
      suppress: isInsideStatementWindow(mid),
    };
  });

  // Cast to the StatementOverlay shape (zod default returns optional fields).
  const statementOverlaySegments: StatementSegment[] = statement_segments.map(
    (s) => ({
      text: s.text,
      start: s.start,
      end: s.end,
      anchor: s.anchor,
      italic_words: s.italic_words ?? [],
    })
  );

  return (
    <AbsoluteFill style={{ backgroundColor: resolvedVibe.color_palette.primary_bg }}>
      {audio_file ? <Audio src={staticFile(audio_file)} /> : null}

      {/* Phase D SFX: each cue plays inside its own time-window so it
          can't bleed into adjacent cues. Volume is per-cue (typically
          0.3-0.5) so SFX sit comfortably under the voiceover. */}
      {sfx_track.map((cue, i) => {
        const startFrame = Math.max(0, Math.round(cue.start_sec * fps));
        const durFrames = Math.max(
          1,
          Math.round(Math.max(0.05, cue.duration_sec) * fps)
        );
        return (
          <Sequence
            key={`sfx-${i}`}
            from={startFrame}
            durationInFrames={durFrames}
            name={`sfx-${cue.intent ?? "cue"}-${i}`}
          >
            <Audio src={staticFile(cue.src)} volume={cue.volume} />
          </Sequence>
        );
      })}

      <Series>
        {scenes.map((scene, i) => {
          const durationFrames = Math.max(1, Math.round(scene.duration_sec * fps));
          return (
            <Series.Sequence
              key={i}
              durationInFrames={durationFrames}
              name={`${scene.type}-${i}`}
            >
              {renderScene(scene, effectiveAccent, i, resolvedVibe)}
            </Series.Sequence>
          );
        })}
      </Series>

      {/* The legacy AvatarOverlay (a floating cutout bust on top of every
          narrator-on-camera scene) has been removed. The avatar now appears
          ONLY in:
            • The opening HookCard scene (bottom-half pane is the avatar's
              real environment photo, no transparent bust overlay).
            • Explicit `avatar_full` scenes inserted by the Python pipeline
              at the two mid-reel positions (full-canvas environment photo).
          Captions still ride on top globally. */}

      {pillWords.length > 0 ? (
        <PillCaption
          words={pillWords}
          accentWords={accent_words}
          accentColor={effectiveAccent}
          bottom={240}
        />
      ) : null}

      {/* Phase C statement-mode overlay. Renders the active full-phrase
          callout when one is in window. PillCaption above is already
          suppressed for the same window via the `suppress` flag. */}
      {statementOverlaySegments.length > 0 ? (
        <StatementOverlay
          segments={statementOverlaySegments}
          accentColor={effectiveAccent}
          textColor={resolvedVibe.color_palette.text_primary}
        />
      ) : null}

      {show_overlays ? (
        <>
          <VignetteOverlay />
          <GrainOverlay />
        </>
      ) : null}
    </AbsoluteFill>
  );
};
