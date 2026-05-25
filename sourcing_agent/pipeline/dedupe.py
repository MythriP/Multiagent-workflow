"""
dedupe.py — Tracks seen story slugs across runs to prevent re-surfacing
the same story. Persists state in seen.json.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


SEEN_PATH = Path(__file__).parent.parent / "seen.json"
RETENTION_DAYS = 14  # purge entries older than this


_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "this", "that", "these", "those", "it", "its",
    "build", "using", "via", "introducing", "new",
}


def _slugify(title: str) -> str:
    """Create a stable, short slug (~40 chars) from a story title."""
    # Strip bracket prefixes like [GitHub Trending], [DeepMind Research]
    title = re.sub(r"^\[.*?\]\s*", "", title)
    # Strip date prefixes like "Apr 30, 2026"
    title = re.sub(r"^[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4}\S*", "", title).strip()
    # Lowercase + remove punctuation
    title = re.sub(r"[^\w\s]", " ", title.lower())
    # Collapse whitespace
    words = title.split()
    # Drop stop words but keep at least 3 words minimum
    meaningful = [w for w in words if w not in _STOP_WORDS]
    if len(meaningful) < 3:
        meaningful = words
    slug = "-".join(meaningful)
    # Hard cap at 50 chars, trim to last whole word
    if len(slug) > 50:
        slug = slug[:50].rsplit("-", 1)[0]
    return slug or "untitled"


class Deduplicator:
    def __init__(self):
        self._data: Dict[str, str] = {}  # slug → ISO timestamp
        self._load()

    def _load(self):
        if SEEN_PATH.exists():
            try:
                with open(SEEN_PATH) as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SEEN_PATH, "w") as f:
            json.dump(self._data, f, indent=2)

    def _purge_old(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        to_delete = []
        for slug, ts in self._data.items():
            try:
                if datetime.fromisoformat(ts).replace(tzinfo=timezone.utc) < cutoff:
                    to_delete.append(slug)
            except Exception:
                pass
        for slug in to_delete:
            del self._data[slug]

    def is_seen(self, title: str) -> bool:
        return _slugify(title) in self._data

    def mark_seen(self, title: str):
        slug = _slugify(title)
        self._data[slug] = datetime.now(timezone.utc).isoformat()

    def filter_new(self, stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return only stories not already in seen.json."""
        return [s for s in stories if not self.is_seen(s.get("title", ""))]

    def mark_batch(self, stories: List[Dict[str, Any]]):
        """Mark a batch of stories as seen and persist."""
        self._purge_old()
        for s in stories:
            self.mark_seen(s.get("title", ""))
        self._save()

    def get_slug(self, title: str) -> str:
        return _slugify(title)
