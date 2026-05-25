# ─── voiceover.py ────────────────────────────────────────────────────────────
# ElevenLabs TTS: narrative text → voiceover.mp3 + word-level timestamps.
#
# Uses the /v1/text-to-speech/{voice_id}/with-timestamps endpoint.
# [pause] markers in the narrative are converted to short silence tokens
# (" ... ") before sending to ElevenLabs so the voice breathes naturally.

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings

log = logging.getLogger(__name__)


@dataclass
class WordTimestamp:
    word: str
    start_sec: float
    end_sec: float

    def to_dict(self) -> dict:
        return {"word": self.word, "start_sec": self.start_sec, "end_sec": self.end_sec}


@dataclass
class VoiceoverResult:
    audio_path: Path | None
    word_timestamps: list[WordTimestamp]
    total_duration_sec: float


def _clean_narrative_for_tts(narrative: str) -> str:
    """Replace [pause] markers with a brief ellipsis pause ElevenLabs handles naturally."""
    cleaned = re.sub(r"\[pause\]", " ... ", narrative)
    # Collapse multiple spaces / newlines
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


def build_fake_word_timestamps(
    narrative: str,
    total_duration_sec: float,
    *,
    min_word_sec: float = 0.18,
) -> list[WordTimestamp]:
    """
    Build approximate per-word timestamps without calling ElevenLabs.

    Used when SKIP_VOICEOVER=true so the global PillCaption can still render
    word-by-word subtitles over the silent video. Words are distributed
    across `total_duration_sec` length-weighted (longer words get longer
    on-screen windows), with a minimum window of `min_word_sec` so single-
    char words don't strobe past the viewer.

    Punctuation-only tokens and pause markers are dropped — the PillCaption
    already filters those, but stripping early keeps the timeline cleaner.
    """
    if not narrative or total_duration_sec <= 0:
        return []

    cleaned = re.sub(r"\[pause\]", " ", narrative)
    raw_words = [w for w in cleaned.split() if w.strip()]
    # Drop pure-ellipsis / pause tokens that would render as empty pills.
    words = [w for w in raw_words if not re.fullmatch(r"\.{2,}|…+", w)]
    if not words:
        return []

    # Length-weighted budget: weight = max(2, len(word)). A two-char word
    # ("is") should still get a noticeable window.
    weights = [max(2, len(w)) for w in words]
    budget_sec = total_duration_sec
    floor_sec = min_word_sec * len(words)
    weight_sec = max(0.0, budget_sec - floor_sec)
    total_weight = sum(weights) or 1

    out: list[WordTimestamp] = []
    cursor = 0.0
    for w, wt in zip(words, weights):
        share = (wt / total_weight) * weight_sec
        dur = min_word_sec + share
        end = cursor + dur
        # Clamp the final word so we never overshoot the audio length.
        if end > total_duration_sec:
            end = total_duration_sec
        out.append(WordTimestamp(word=w, start_sec=round(cursor, 3), end_sec=round(end, 3)))
        cursor = end

    return out


def _alignment_to_words(
    chars: list[str],
    start_times_sec: list[float],
    end_times_sec: list[float],
) -> list[WordTimestamp]:
    """
    Convert ElevenLabs character alignment to word-level timestamps.

    The SDK returns a CharacterAlignmentResponseModel with:
        .characters                  — list of single characters
        .character_start_times_seconds — start time per char (seconds)
        .character_end_times_seconds   — end time per char (seconds)

    We group consecutive non-whitespace characters into words, taking the
    first char's start time and the last char's end time for each word.
    """
    words: list[WordTimestamp] = []
    cur_chars: list[str] = []
    cur_start: float = 0.0
    cur_end: float = 0.0

    for ch, start, end in zip(chars, start_times_sec, end_times_sec):
        if ch in (" ", "\n", "\t"):
            if cur_chars:
                words.append(
                    WordTimestamp(
                        word="".join(cur_chars),
                        start_sec=round(cur_start, 3),
                        end_sec=round(cur_end, 3),
                    )
                )
                cur_chars = []
        else:
            if not cur_chars:
                cur_start = start
            cur_chars.append(ch)
            cur_end = end

    if cur_chars:
        words.append(
            WordTimestamp(
                word="".join(cur_chars),
                start_sec=round(cur_start, 3),
                end_sec=round(cur_end, 3),
            )
        )

    return words


def generate_voiceover(
    narrative: str,
    out_dir: Path,
    elevenlabs_api_key: str,
    voice_id: str,
    model_id: str = "eleven_turbo_v2_5",
) -> VoiceoverResult:
    """
    Convert narrative text to speech via ElevenLabs with-timestamps endpoint.
    Saves voiceover.mp3 and word_timestamps.json to out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tts_text = _clean_narrative_for_tts(narrative)

    log.info("━━ Voiceover: %d chars → ElevenLabs (voice=%s, model=%s)...",
             len(tts_text), voice_id, model_id)

    client = ElevenLabs(api_key=elevenlabs_api_key)

    response = client.text_to_speech.convert_with_timestamps(
        voice_id=voice_id,
        text=tts_text,
        model_id=model_id,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.45,
            similarity_boost=0.82,
            style=0.25,
            use_speaker_boost=True,
        ),
    )

    # Decode audio (field is audio_base_64 in the SDK response object)
    import base64 as _b64
    audio_b64: str = response.audio_base_64 or ""
    if not audio_b64:
        raise ValueError("ElevenLabs response missing audio_base_64")

    audio_bytes = _b64.b64decode(audio_b64)
    audio_path = out_dir / "voiceover.mp3"
    audio_path.write_bytes(audio_bytes)
    log.info("✅ voiceover.mp3 saved (%.1f KB)", len(audio_bytes) / 1024)

    # Parse alignment.
    # SDK model: CharacterAlignmentResponseModel with fields:
    #   .characters                    list[str]
    #   .character_start_times_seconds list[float]
    #   .character_end_times_seconds   list[float]
    alignment = response.alignment
    word_timestamps: list[WordTimestamp] = []

    if alignment and alignment.characters:
        word_timestamps = _alignment_to_words(
            chars=list(alignment.characters),
            start_times_sec=list(alignment.character_start_times_seconds or []),
            end_times_sec=list(alignment.character_end_times_seconds or []),
        )
    else:
        # Try normalized_alignment (same field shape)
        norm = response.normalized_alignment
        if norm and norm.characters:
            word_timestamps = _alignment_to_words(
                chars=list(norm.characters),
                start_times_sec=list(norm.character_start_times_seconds or []),
                end_times_sec=list(norm.character_end_times_seconds or []),
            )
        else:
            log.warning("No character alignment in ElevenLabs response — timing will be estimated")

    total_sec = word_timestamps[-1].end_sec if word_timestamps else len(tts_text) / 14.0

    # Save timestamps for scene_writer
    ts_path = out_dir / "word_timestamps.json"
    ts_path.write_text(
        json.dumps([wt.to_dict() for wt in word_timestamps], indent=2)
    )
    log.info("✅ word_timestamps.json saved (%d words, %.1fs total)", len(word_timestamps), total_sec)

    return VoiceoverResult(
        audio_path=audio_path,
        word_timestamps=word_timestamps,
        total_duration_sec=total_sec,
    )
