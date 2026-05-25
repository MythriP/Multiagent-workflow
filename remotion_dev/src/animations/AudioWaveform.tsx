// Real-time audio waveform visualizer powered by @remotion/media-utils.
// Displays an equalizer-style bar chart driven by the actual audio frequency
// data at each rendered frame. Pass the voiceover src.

import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";
import { BRAND } from "../brand";

interface AudioWaveformProps {
  src: string;
  barCount?: number;
  color?: string;
  height?: number;
  /** 'speed' is faster; 'accuracy' gives finer frequency detail */
  optimizeFor?: "speed" | "accuracy";
  style?: React.CSSProperties;
}

export const AudioWaveform: React.FC<AudioWaveformProps> = ({
  src,
  barCount = 64,
  color = BRAND.accent,
  height = 90,
  optimizeFor = "speed",
  style,
}) => {
  const audioData = useAudioData(src);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!audioData) {
    // Placeholder bars while loading
    return (
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 2,
          height,
          ...style,
        }}
      >
        {Array.from({ length: barCount }, (_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 2,
              backgroundColor: color,
              borderRadius: 2,
              opacity: 0.2,
            }}
          />
        ))}
      </div>
    );
  }

  const bands = visualizeAudio({
    audioData,
    frame,
    fps,
    numberOfSamples: barCount,
    optimizeFor,
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 2,
        height,
        ...style,
      }}
    >
      {bands.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: `${Math.max(0.02, v) * 100}%`,
            minHeight: 2,
            backgroundColor: color,
            borderRadius: 2,
            opacity: 0.85 + v * 0.15,
          }}
        />
      ))}
    </div>
  );
};
