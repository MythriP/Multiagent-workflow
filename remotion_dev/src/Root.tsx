import "./index.css";
import { Composition } from "remotion";
import { BRAND } from "./brand";

// ── Static slide templates (carousel output, 4:5 portrait) ───────────────────
import { CoverSlide, coverSlideSchema } from "./templates/CoverSlide/CoverSlide";
import { BodySlide, bodySlideSchema } from "./templates/BodySlide/BodySlide";
import { EmbedSlide, embedSlideSchema } from "./templates/EmbedSlide/EmbedSlide";
import { CloserSlide, closerSlideSchema } from "./templates/CloserSlide/CloserSlide";
import {
  SlideCarousel,
  slideCarouselSchema,
  DEMO_CAROUSEL_PROPS,
} from "./templates/SlideCarousel/SlideCarousel";

// ── Animated video composition (9:16 vertical — primary format) ──────────────
import {
  AnimatedVideo,
  animatedVideoSchema,
  calculateMetadata,
} from "./compositions/AnimatedVideo";

// ── DynamicReel composition (9:16 vertical — production pipeline) ────────────
//     The script_agent → render.py → npm run render-video pipeline targets
//     this composition. The legacy AnimatedVideo above is kept for backward
//     compatibility with older topic.json files.
import {
  DynamicReel,
  dynamicReelSchema,
  calculateMetadata as calcDynamicReelMetadata,
} from "./DynamicReel";

const VW = BRAND.video.width;     // 1080
const VH = BRAND.video.height;    // 1920 (9:16 vertical)
const SW = BRAND.slide.width;     // 1080
const SH = BRAND.slide.height;    // 1350 (4:5 portrait)
const FPS = 30;

const DEMO_IMAGE =
  "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1280px-The_Earth_seen_from_Apollo_17.jpg";

const DEMO_IMAGE_2 =
  "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1280px-Cat03.jpg";

const DEMO_IMAGE_3 =
  "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1280px-Cat_November_2010-1a.jpg";

// ── Demo video script for Remotion Studio preview ────────────────────────────
const DEMO_VIDEO_PROPS = {
  topic: "Anthropic's Mythos Model Leaked",
  slug: "anthropic-mythos-leak",
  accent_color: BRAND.accentSecondary,
  audio_file: undefined,
  word_timestamps: [],
  show_captions: true,
  scenes: [
    {
      type: "hook" as const,
      duration_sec: 5,
      headline: "Anthropic built a cyberweapon. Then it leaked.",
      accent_words: ["cyberweapon", "leaked"],
    },
    {
      type: "kinetic_type" as const,
      duration_sec: 4,
      text: "Internally called Mythos.",
      accent_words: ["Mythos"],
      words_per_burst: 1,
    },
    {
      type: "context" as const,
      duration_sec: 6,
      lines: [
        "The model could hack every major OS and browser.",
        'Anthropic called it "too dangerous to release."',
      ],
      source_label: "Bloomberg",
    },
    {
      type: "broll_montage" as const,
      duration_sec: 5,
      images: [DEMO_IMAGE, DEMO_IMAGE_2, DEMO_IMAGE_3, DEMO_IMAGE_2],
      captions: ["Windows", "macOS", "Linux", "All of them"],
      title: "OS COVERAGE",
    },
    {
      type: "stat" as const,
      duration_sec: 4,
      number: 3,
      label: "Operating systems compromised",
      prefix: "",
      suffix: "",
      context_line: "Windows · macOS · Linux — all of them.",
    },
    {
      type: "quote" as const,
      duration_sec: 6,
      text: "We cannot let advanced capabilities exist without advanced safety.",
      speaker: "Dario Amodei",
      role: "CEO, Anthropic",
    },
    {
      type: "outro" as const,
      duration_sec: 3,
      cta: "Follow for more AI drops.",
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* ─── PRIMARY: DynamicReel (production pipeline, 9:16 vertical) ─── */}
      <Composition
        id="DynamicReel"
        component={DynamicReel}
        // Fallback duration; overridden by calculateMetadata at render time.
        durationInFrames={FPS * 30}
        fps={FPS}
        width={VW}
        height={VH}
        schema={dynamicReelSchema}
        calculateMetadata={calcDynamicReelMetadata}
        defaultProps={{
          topic: "Demo Reel",
          slug: "demo-reel",
          accent_color: "#FF3D71",
          audio_file: null,
          word_timestamps: [],
          accent_words: [],
          show_overlays: true,
          statement_segments: [],
          sfx_track: [],
          scenes: [
            {
              type: "hook" as const,
              duration_sec: 3,
              hook: "Hello world",
              subtitle: "DynamicReel demo",
            },
            {
              type: "cta" as const,
              duration_sec: 2,
              text: "Follow for more.",
            },
          ],
        }}
      />

      {/* ─── LEGACY ──────────────────────────────────────────────────────
       *
       * The compositions below ("AnimatedVideo", "SlideCarousel",
       * "CoverSlide", "BodySlideWithImage", "BodySlideTextOnly",
       * "EmbedSlide", "CloserSlide") are NOT used by the script_agent
       * production pipeline today. They render the older "post slides"
       * format via `npm run render-post` (`scripts/render-post.ts` +
       * `src/templates/*` + `src/compositions/AnimatedVideo.tsx`).
       *
       * Kept intentionally for possible future use. If you're adding a
       * new scene for the main reel, work in DynamicReel above instead.
       * ────────────────────────────────────────────────────────────── */}
      <Composition
        id="AnimatedVideo"
        component={AnimatedVideo}
        calculateMetadata={calculateMetadata}
        durationInFrames={
          DEMO_VIDEO_PROPS.scenes.reduce((s, sc) => s + sc.duration_sec, 0) * FPS
        }
        fps={FPS}
        width={VW}
        height={VH}
        schema={animatedVideoSchema}
        defaultProps={DEMO_VIDEO_PROPS}
      />

      {/* ─── Static slide templates (carousel output, 4:5 portrait) ───── */}

      <Composition
        id="SlideCarousel"
        component={SlideCarousel}
        durationInFrames={DEMO_CAROUSEL_PROPS.slides.length * DEMO_CAROUSEL_PROPS.framesPerSlide}
        fps={FPS}
        width={SW}
        height={SH}
        schema={slideCarouselSchema}
        defaultProps={DEMO_CAROUSEL_PROPS}
      />

      <Composition
        id="CoverSlide"
        component={CoverSlide}
        durationInFrames={90}
        fps={FPS}
        width={SW}
        height={SH}
        schema={coverSlideSchema}
        defaultProps={{
          headline: 'HACKERS HAVE BREACHED ANTHROPIC\'S "TOO DANGEROUS TO RELEASE" MYTHOS AI MODEL',
          accentWords: ["ANTHROPIC'S", "MYTHOS AI MODEL"],
          tagline: "THE LINE BETWEEN SAFETY AND VULNERABILITY JUST GOT THINNER",
          heroImage: DEMO_IMAGE,
          ctaLabel: "SWIPE",
          accentColor: BRAND.accentSecondary,
        }}
      />

      <Composition
        id="BodySlideWithImage"
        component={BodySlide}
        durationInFrames={90}
        fps={FPS}
        width={SW}
        height={SH}
        schema={bodySlideSchema}
        defaultProps={{
          lines: [
            "Matt Cortland realized something strange.",
            "",
            "There was no official data on Guinness prices anymore.",
            "",
            "So instead of guessing, he decided to track it himself.",
          ],
          image: DEMO_IMAGE,
          accentColor: BRAND.accent,
        }}
      />

      <Composition
        id="BodySlideTextOnly"
        component={BodySlide}
        durationInFrames={90}
        fps={FPS}
        width={SW}
        height={SH}
        schema={bodySlideSchema}
        defaultProps={{
          lines: [
            "> anthropic builds a cyberweapon",
            "> calls it mythos",
            '> "can hack every major OS and browser"',
            '> dario: "we\'re the safe & responsible ai lab"',
            '> "can\'t release it to the public"',
            "> Mercor (their training contractor) gets breached",
          ],
          accentColor: BRAND.accentSecondary,
        }}
      />

      <Composition
        id="EmbedSlide"
        component={EmbedSlide}
        durationInFrames={90}
        fps={FPS}
        width={SW}
        height={SH}
        schema={embedSlideSchema}
        defaultProps={{
          contextText: "Here's the original Bloomberg report that broke the story:",
          embedImage: DEMO_IMAGE,
          captionText: "",
          accentColor: BRAND.accentSecondary,
        }}
      />

      <Composition
        id="CloserSlide"
        component={CloserSlide}
        durationInFrames={90}
        fps={FPS}
        width={SW}
        height={SH}
        schema={closerSlideSchema}
        defaultProps={{
          lines: ["Follow for more."],
          accentWords: [],
          accentColor: BRAND.accentSecondary,
        }}
      />
    </>
  );
};
