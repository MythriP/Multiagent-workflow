#!/usr/bin/env tsx
// ─── render-post ─────────────────────────────────────────────────────────────
// Reads a post.json file, renders every slide as a PNG via Remotion's
// programmatic API, and writes the output to:
//
//     results/textposts/YYYY-MM-DD/<slug>/
//        ├── slide-01.png
//        ├── slide-02.png
//        ├── ...
//        ├── caption.txt
//        ├── hashtags.txt
//        └── post.json   (the original input, copied for reproducibility)
//
// Usage:
//     npm run render-post -- inputs/example-post.json
//     npm run render-post -- path/to/any-post.json

import fs from "node:fs";
import path from "node:path";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { postJsonSchema, type PostJson, type SlideEntry } from "./types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function todayISO(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

// Picks the right Composition ID for each slide.
// Body slides have two registered compositions: with-image and text-only.
// We pick based on whether `image` is provided.
function compositionIdFor(slide: SlideEntry): string {
  switch (slide.type) {
    case "cover":
      return "CoverSlide";
    case "body":
      return slide.props.image ? "BodySlideWithImage" : "BodySlideTextOnly";
    case "embed":
      return "EmbedSlide";
    case "closer":
      return "CloserSlide";
  }
}

function normalizeHashtag(tag: string): string {
  const t = tag.trim();
  return t.startsWith("#") ? t : `#${t}`;
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error("Usage: npm run render-post -- <path-to-post.json>");
    process.exit(1);
  }

  const absInputPath = path.resolve(inputPath);
  if (!fs.existsSync(absInputPath)) {
    console.error(`File not found: ${absInputPath}`);
    process.exit(1);
  }

  // ─── Parse + validate the post JSON ────────────────────────────────────────
  const rawJson = fs.readFileSync(absInputPath, "utf-8");
  let parsed: PostJson;
  try {
    parsed = postJsonSchema.parse(JSON.parse(rawJson));
  } catch (err) {
    console.error("Invalid post.json:");
    console.error(err);
    process.exit(1);
  }

  const { topic, slug, slides, caption, hashtags } = parsed;

  // ─── Set up output directory ───────────────────────────────────────────────
  const date = todayISO();
  const outDir = path.resolve("results", "textposts", date, slug);
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`\n📦 Rendering post: ${topic}`);
  console.log(`   Slug:    ${slug}`);
  console.log(`   Date:    ${date}`);
  console.log(`   Slides:  ${slides.length}`);
  console.log(`   Output:  ${outDir}\n`);

  // ─── Bundle the Remotion project once ──────────────────────────────────────
  console.log("⏳ Bundling Remotion project (one-time cost)...");
  const bundleStart = Date.now();
  const bundleLocation = await bundle({
    entryPoint: path.resolve("src/index.ts"),
    webpackOverride: (cfg) => cfg,
  });
  console.log(`✅ Bundled in ${((Date.now() - bundleStart) / 1000).toFixed(1)}s\n`);

  // ─── Render each slide ─────────────────────────────────────────────────────
  for (let i = 0; i < slides.length; i++) {
    const slide = slides[i];
    const compositionId = compositionIdFor(slide);
    const slideNum = i + 1;
    const outFile = path.join(outDir, `slide-${pad2(slideNum)}.png`);

    process.stdout.write(
      `  [${pad2(slideNum)}/${pad2(slides.length)}] ${compositionId.padEnd(20)} → ${path.basename(outFile)} ... `
    );

    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: compositionId,
      inputProps: slide.props as Record<string, unknown>,
    });

    const renderStart = Date.now();
    await renderStill({
      composition,
      serveUrl: bundleLocation,
      output: outFile,
      inputProps: slide.props as Record<string, unknown>,
      imageFormat: "png",
    });
    console.log(`done (${((Date.now() - renderStart) / 1000).toFixed(1)}s)`);
  }

  // ─── Write caption.txt + hashtags.txt + copy post.json ─────────────────────
  fs.writeFileSync(path.join(outDir, "caption.txt"), caption.trim() + "\n");

  const tagsLine = hashtags.map(normalizeHashtag).join(" ");
  fs.writeFileSync(path.join(outDir, "hashtags.txt"), tagsLine + "\n");

  fs.copyFileSync(absInputPath, path.join(outDir, "post.json"));

  console.log(`\n✅ Done — ${slides.length} slides + caption + hashtags`);
  console.log(`   ${outDir}\n`);
}

main().catch((err) => {
  console.error("\n❌ Render failed:");
  console.error(err);
  process.exit(1);
});
