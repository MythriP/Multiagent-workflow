// AnimatedVideo — top-level composition consumed by renderMedia.
//
// Props are a full VideoScript object (video_script.json).
// Duration is calculated dynamically from the sum of scene duration_sec fields
// via calculateMetadata, so the durationInFrames registered in Root.tsx is
// only a fallback used by Remotion Studio before the first render.
//
// CaptionTrack is overlaid globally above all scenes when word_timestamps is
// present and show_captions is true — this is the single biggest quality
// lever for matching reactive-creator style.

import React from "react";
import { AbsoluteFill, Audio, Series, staticFile, useVideoConfig } from "remotion";
import { z } from "zod";
import { videoScriptSchema } from "../video-types";
import type { Scene } from "../video-types";

// Scene components
import { HookScene } from "../scenes/HookScene";
import { ContextScene } from "../scenes/ContextScene";
import { BodyScene } from "../scenes/BodyScene";
import { PaperScene } from "../scenes/PaperScene";
import { StatScene } from "../scenes/StatScene";
import { QuoteScene } from "../scenes/QuoteScene";
import { TimelineScene } from "../scenes/TimelineScene";
import { CompareScene } from "../scenes/CompareScene";
import { OutroScene } from "../scenes/OutroScene";
import { BRollMontageScene } from "../scenes/BRollMontageScene";
import { KineticTypeScene } from "../scenes/KineticTypeScene";
import { WebScrollScene } from "../scenes/WebScrollScene";

// Global caption overlay
import { CaptionTrack } from "../animations/CaptionTrack";

// ─── Schema exposed for Root.tsx Composition registration ────────────────────

export const animatedVideoSchema = videoScriptSchema;

// ─── calculateMetadata ────────────────────────────────────────────────────────

export const calculateMetadata = ({
  props,
}: {
  props: z.infer<typeof animatedVideoSchema>;
}) => {
  const fps = 30;
  const totalSec = props.scenes.reduce((s, scene) => s + scene.duration_sec, 0);
  return {
    durationInFrames: Math.max(1, Math.round(totalSec * fps)),
    fps,
  };
};

// ─── Scene dispatcher ────────────────────────────────────────────────────────

function renderScene(
  scene: Scene,
  accentColor: string,
  durationFrames: number
): React.ReactNode {
  const base = { accentColor, durationFrames };
  switch (scene.type) {
    case "hook":            return <HookScene           {...scene} {...base} />;
    case "context":         return <ContextScene        {...scene} {...base} />;
    case "body":            return <BodyScene           {...scene} {...base} />;
    case "paper":           return <PaperScene          {...scene} {...base} />;
    case "stat":            return <StatScene           {...scene} {...base} />;
    case "quote":           return <QuoteScene          {...scene} {...base} />;
    case "timeline":        return <TimelineScene       {...scene} {...base} />;
    case "compare":         return <CompareScene        {...scene} {...base} />;
    case "outro":           return <OutroScene          {...scene} {...base} />;
    case "broll_montage":   return <BRollMontageScene   {...scene} {...base} />;
    case "kinetic_type":    return <KineticTypeScene    {...scene} {...base} />;
    case "web_scroll":      return <WebScrollScene      {...scene} {...base} />;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

export const AnimatedVideo: React.FC<z.infer<typeof animatedVideoSchema>> = (
  script
) => {
  const { fps } = useVideoConfig();

  const captionsEnabled =
    script.show_captions !== false &&
    script.word_timestamps &&
    script.word_timestamps.length > 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "#0A0A0A" }}>
      {/* Voiceover track */}
      {script.audio_file && (
        <Audio src={staticFile(script.audio_file)} />
      )}

      {/* Scene sequence */}
      <Series>
        {script.scenes.map((scene, i) => {
          const durationFrames = Math.max(1, Math.round(scene.duration_sec * fps));
          return (
            <Series.Sequence
              key={i}
              durationInFrames={durationFrames}
              name={`${scene.type}-${i}`}
            >
              {renderScene(scene, script.accent_color, durationFrames)}
            </Series.Sequence>
          );
        })}
      </Series>

      {/* Global word-by-word caption overlay (drives reactive-creator energy) */}
      {captionsEnabled && (
        <CaptionTrack
          words={script.word_timestamps}
          accentColor={script.accent_color}
        />
      )}
    </AbsoluteFill>
  );
};
