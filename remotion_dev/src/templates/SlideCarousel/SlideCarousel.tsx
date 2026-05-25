import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { z } from "zod";
import { BRAND } from "../../brand";
import { CoverSlide, coverSlideSchema } from "../CoverSlide/CoverSlide";
import { BodySlide, bodySlideSchema } from "../BodySlide/BodySlide";
import { EmbedSlide, embedSlideSchema } from "../EmbedSlide/EmbedSlide";
import { CloserSlide, closerSlideSchema } from "../CloserSlide/CloserSlide";

// Each slide in the carousel is a discriminated union by type
const slideSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("cover"), props: coverSlideSchema }),
  z.object({ type: z.literal("body"), props: bodySlideSchema }),
  z.object({ type: z.literal("embed"), props: embedSlideSchema }),
  z.object({ type: z.literal("closer"), props: closerSlideSchema }),
]);

export const slideCarouselSchema = z.object({
  slides: z.array(slideSchema),
  // How many frames each slide is displayed (for preview purposes)
  framesPerSlide: z.number().default(90),
});

export type SlideCarouselProps = z.infer<typeof slideCarouselSchema>;

export const SlideCarousel: React.FC<SlideCarouselProps> = ({
  slides,
  framesPerSlide,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: BRAND.background }}>
      <Series>
        {slides.map((slide, i) => (
          <Series.Sequence key={i} durationInFrames={framesPerSlide} name={`Slide ${i + 1}`}>
            {slide.type === "cover" && <CoverSlide {...slide.props} />}
            {slide.type === "body" && <BodySlide {...slide.props} />}
            {slide.type === "embed" && <EmbedSlide {...slide.props} />}
            {slide.type === "closer" && <CloserSlide {...slide.props} />}
          </Series.Sequence>
        ))}
      </Series>
    </AbsoluteFill>
  );
};

// ─── Demo data (Anthropic Mythos story — based on uncover.ai example) ──────────
// Uses placeholder image URLs — swap with real images when available.
export const DEMO_CAROUSEL_PROPS: SlideCarouselProps = {
  framesPerSlide: 90,
  slides: [
    {
      type: "cover",
      props: {
        headline: 'HACKERS HAVE BREACHED ANTHROPIC\'S "TOO DANGEROUS TO RELEASE" MYTHOS AI MODEL',
        accentWords: ["ANTHROPIC'S", '"TOO DANGEROUS TO RELEASE"', "MYTHOS AI MODEL"],
        tagline: "THE LINE BETWEEN SAFETY AND VULNERABILITY JUST GOT THINNER",
        heroImage: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1280px-The_Earth_seen_from_Apollo_17.jpg",
        ctaLabel: "SWIPE",
        accentColor: BRAND.accentSecondary,
      },
    },
    {
      type: "embed",
      props: {
        contextText: "Here's the tweet that started it all:",
        embedImage: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1280px-The_Earth_seen_from_Apollo_17.jpg",
        captionText: "",
        accentColor: BRAND.accentSecondary,
      },
    },
    {
      type: "body",
      props: {
        lines: [
          "> anthropic builds a cyberweapon",
          "> calls it mythos",
          "> \"can hack every major OS and browser\"",
          "> dario: \"we're the safe & responsible ai lab\"",
          "> \"can't release it to the public\"",
          "> Mercor (their training contractor) gets breached",
        ],
        accentColor: BRAND.accentSecondary,
      },
    },
    {
      type: "body",
      props: {
        lines: [
          "> leaks anthropic's model naming conventions",
          "> hackers guess the URL pattern",
          "> contractor credentials still work",
          "> they're inside",
          "",
          "The group also has access to other unreleased Anthropic models.",
          "",
          "Not just Mythos. The whole pipeline.",
        ],
        accentColor: BRAND.accentSecondary,
      },
    },
    {
      type: "body",
      props: {
        lines: [
          "Anthropic's statement: \"investigating a report of access through one of our third-party vendor environments.\"",
          "",
          "Mythos got breached on day one 💀",
        ],
        image: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1280px-The_Earth_seen_from_Apollo_17.jpg",
        accentColor: BRAND.accentSecondary,
      },
    },
    {
      type: "closer",
      props: {
        lines: [
          "Follow for more.",
        ],
        accentWords: [],
        accentColor: BRAND.accentSecondary,
      },
    },
  ],
};
