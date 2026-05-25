// CaptionTrack — global word-by-word voiceover captions.
//
// Reads ElevenLabs word_timestamps and renders the currently-spoken phrase
// near the bottom of the frame (above platform UI safe-zone). The word being
// spoken at the current frame is highlighted in accent color with a slight
// scale punch; previously-spoken words in the same line remain bright; future
// words are dim. Phrases auto-wrap so we never show more than
// `maxWordsPerLine` at once.
//
// This is the single biggest quality lever for matching reactive-creator
// style (Varun Mayya, 100xEngineers, Riley Brown) — captions sync the
// viewer's eye to the audio and dramatically increase retention.

import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { BRAND } from "../brand";
import type { WordTimestamp } from "../video-types";

interface CaptionTrackProps {
  words: WordTimestamp[];
  accentColor: string;
  maxWordsPerLine?: number;
  fontSize?: number;
  bottomOffset?: number;
}

export const CaptionTrack: React.FC<CaptionTrackProps> = ({
  words,
  accentColor,
  maxWordsPerLine = BRAND.caption.maxWordsPerLine,
  fontSize = BRAND.fontSize.caption,
  bottomOffset = BRAND.caption.bottomOffset,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const tSec = frame / fps;

  if (!words || words.length === 0) return null;

  // ── Group words into fixed-size phrase chunks ─────────────────────────
  const phrases: WordTimestamp[][] = [];
  for (let i = 0; i < words.length; i += maxWordsPerLine) {
    phrases.push(words.slice(i, i + maxWordsPerLine));
  }

  // ── Find the phrase that contains the current playhead time ───────────
  let activePhraseIndex = -1;
  for (let i = 0; i < phrases.length; i++) {
    const p = phrases[i];
    const startSec = p[0].start_sec;
    const endSec = p[p.length - 1].end_sec;
    if (tSec >= startSec - 0.05 && tSec <= endSec + 0.25) {
      activePhraseIndex = i;
      break;
    }
  }

  // If we're between phrases, try to keep the most recent one visible
  // briefly so transitions feel smooth (no popping out).
  if (activePhraseIndex === -1) {
    for (let i = phrases.length - 1; i >= 0; i--) {
      const endSec = phrases[i][phrases[i].length - 1].end_sec;
      if (tSec > endSec && tSec < endSec + 0.3) {
        activePhraseIndex = i;
        break;
      }
    }
  }

  if (activePhraseIndex === -1) return null;

  const phrase = phrases[activePhraseIndex];

  // Phrase box fade in/out (200ms each side)
  const phraseStartSec = phrase[0].start_sec;
  const phraseEndSec = phrase[phrase.length - 1].end_sec;
  const fadeFrames = Math.round(fps * 0.18);
  const opacity = interpolate(
    frame,
    [
      Math.round(phraseStartSec * fps) - fadeFrames,
      Math.round(phraseStartSec * fps),
      Math.round(phraseEndSec * fps),
      Math.round(phraseEndSec * fps) + fadeFrames,
    ],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: bottomOffset,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        opacity,
      }}
    >
      <div
        style={{
          maxWidth: width - 80,
          backgroundColor: BRAND.caption.backgroundColor,
          borderRadius: BRAND.caption.borderRadius,
          padding: `${BRAND.caption.paddingY}px ${BRAND.caption.paddingX}px`,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0.32em",
          boxShadow: "0 8px 30px rgba(0,0,0,0.6)",
        }}
      >
        {phrase.map((w, i) => {
          const isActive = tSec >= w.start_sec - 0.02 && tSec <= w.end_sec + 0.05;
          const isPast = tSec > w.end_sec + 0.05;

          // Punch scale at the moment the word is spoken
          const punchProgress = isActive
            ? interpolate(
                tSec,
                [w.start_sec, w.start_sec + 0.08, w.end_sec],
                [0, 1, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              )
            : isPast
              ? 1
              : 0;
          const scale = 1 + punchProgress * 0.08;

          const color = isActive
            ? accentColor
            : isPast
              ? BRAND.textPrimary
              : BRAND.textDim;

          return (
            <span
              key={i}
              style={{
                fontFamily: BRAND.fontSans,
                fontSize,
                fontWeight: 800,
                color,
                letterSpacing: "-0.01em",
                lineHeight: 1.15,
                transform: `scale(${scale})`,
                transformOrigin: "center",
                textShadow: isActive ? `0 0 18px ${accentColor}55` : "none",
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
