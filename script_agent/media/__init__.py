"""Media subpackage for script_agent.

Groups every external media interaction into one namespace:

- `core`       - inventory + per-beat orchestration (was top-level `media.py`).
- `pexels`     - Pexels stock photo/video search.
- `fal_image`  - fal.ai photoreal image generation.
- `video_gen`  - Veo 3.1 Fast / generic AI video generation via fal.ai.
- `voiceover`  - ElevenLabs TTS + word timestamping.
- `lipsync`    - fal.ai talking-avatar lipsync segments.
- `sfx`        - sound-effect cue building for the render layer.
"""

from .core import (
    MediaResult,
    build_media_inventory_text,
    execute_beat_media,
    process_media,
)

__all__ = [
    "MediaResult",
    "build_media_inventory_text",
    "execute_beat_media",
    "process_media",
]
