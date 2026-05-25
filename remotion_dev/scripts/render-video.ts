#!/usr/bin/env tsx
// ─── render-video ────────────────────────────────────────────────────────────
// Reads a video_script.json file, renders the DynamicReel composition as an
// H.264 MP4 via Remotion's programmatic renderMedia API, and writes output to:
//
//     <repo>/content_gen/remotion_dev/outputs/videos/YYYY-MM-DD/HH-MM/<slug>/
//        ├── video.mp4
//        └── video_script.json   (copy of input for reproducibility)
//
// (The output path may be overridden via the REEL_OUTPUT_ROOT env var; if
// unset, we default to the canonical content_gen/remotion_dev location so
// every renderer in the project drops files in the same place.)
//
// This mirrors the YYYY-MM-DD/HH-MM/<slug>/ convention used by sourcing_agent
// and script_agent so all pipeline outputs share the same folder shape.
//
// Duration is determined automatically by calculateMetadata on DynamicReel.
//
// Usage:
//     npm run render-video -- path/to/video_script.json

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { dynamicReelSchema } from "../src/DynamicReel";

// ESM-safe __dirname (tsx runs scripts in ESM mode where the CommonJS
// __dirname is not defined).
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── Helpers ──────────────────────────────────────────────────────────────────

function todayISO(): string {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

function nowHHMM(): string {
  const d = new Date();
  return (
    String(d.getHours()).padStart(2, "0") +
    "-" +
    String(d.getMinutes()).padStart(2, "0")
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const inputPath = process.argv[2];
  if (!inputPath) {
    console.error("Usage: npm run render-video -- <path-to-video_script.json>");
    process.exit(1);
  }

  const absInputPath = path.resolve(inputPath);
  if (!fs.existsSync(absInputPath)) {
    console.error(`File not found: ${absInputPath}`);
    process.exit(1);
  }

  // ─── Parse + validate ────────────────────────────────────────────────────
  const rawJson = fs.readFileSync(absInputPath, "utf-8");
  let script: ReturnType<typeof dynamicReelSchema.parse>;
  try {
    script = dynamicReelSchema.parse(JSON.parse(rawJson));
  } catch (err) {
    console.error("Invalid video_script.json:");
    console.error(err);
    process.exit(1);
  }

  // ─── Output directory ────────────────────────────────────────────────────
  // Canonical pipeline output: <repo>/content_gen/remotion_dev/outputs/videos.
  // This script lives at <repo>/content_gen/remotion_dev/scripts/render-video.ts,
  // so the canonical output root is one level up + outputs/videos.
  const date = todayISO();
  const time = nowHHMM();
  const defaultRoot = path.resolve(
    __dirname,
    "..", // -> remotion_dev
    "outputs",
    "videos"
  );
  const outRoot = process.env.REEL_OUTPUT_ROOT
    ? path.resolve(process.env.REEL_OUTPUT_ROOT)
    : defaultRoot;
  const outDir = path.join(outRoot, date, time, script.slug);
  fs.mkdirSync(outDir, { recursive: true });

  const outFile = path.join(outDir, "video.mp4");
  const totalSec = script.scenes.reduce((s, sc) => s + sc.duration_sec, 0);

  console.log(`\n🎬 Rendering DynamicReel: ${script.topic}`);
  console.log(`   Slug:     ${script.slug}`);
  console.log(`   Date:     ${date}  ${time}`);
  console.log(`   Scenes:   ${script.scenes.length}`);
  console.log(`   Duration: ${totalSec.toFixed(2)}s`);
  console.log(`   Output:   ${outFile}\n`);

  // ─── Bundle Remotion project ─────────────────────────────────────────────
  console.log("⏳ Bundling Remotion project...");
  const bundleStart = Date.now();
  const bundleLocation = await bundle({
    entryPoint: path.resolve("src/index.ts"),
    webpackOverride: (cfg) => cfg,
  });
  console.log(`✅ Bundled in ${((Date.now() - bundleStart) / 1000).toFixed(1)}s\n`);

  // ─── Select composition (triggers calculateMetadata) ─────────────────────
  console.log("⏳ Resolving composition metadata...");
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "DynamicReel",
    inputProps: script as unknown as Record<string, unknown>,
  });
  console.log(
    `   → ${composition.durationInFrames} frames @ ${composition.fps} fps ` +
      `(${(composition.durationInFrames / composition.fps).toFixed(1)}s)\n`
  );

  // ─── Render MP4 ──────────────────────────────────────────────────────────
  console.log("🎥 Rendering video...");
  const renderStart = Date.now();

  let lastProgress = -1;
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outFile,
    inputProps: script as unknown as Record<string, unknown>,
    imageFormat: "jpeg",
    jpegQuality: 95,
    crf: 18,
    onProgress: ({ progress }) => {
      const pct = Math.floor(progress * 100);
      if (pct !== lastProgress && pct % 5 === 0) {
        process.stdout.write(`\r   ${pct}% complete...`);
        lastProgress = pct;
      }
    },
  });

  process.stdout.write("\r");
  const elapsed = ((Date.now() - renderStart) / 1000).toFixed(1);
  const size = formatBytes(fs.statSync(outFile).size);
  console.log(`✅ Rendered in ${elapsed}s  (${size})\n`);

  // ─── Copy video_script.json alongside the output ──────────────────────────
  fs.copyFileSync(absInputPath, path.join(outDir, "video_script.json"));

  console.log(`📁 Output: ${outDir}`);
  console.log(`   video.mp4`);
  console.log(`   video_script.json\n`);
}

main().catch((err) => {
  console.error("\n❌ Render failed:");
  console.error(err);
  process.exit(1);
});
