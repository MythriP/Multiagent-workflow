"""
HuggingFace Daily Papers — curated trending ML papers, refreshed daily.

Uses the public JSON API at https://huggingface.co/api/daily_papers which
returns the same papers shown on https://huggingface.co/papers/date/<YYYY-MM-DD>.

The endpoint defaults to today's papers; we filter to entries submitted within
the last ~36 hours to keep the queue reactive (per the user's "near today or
yesterday" requirement).
"""

import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


API_URL = "https://huggingface.co/api/daily_papers"
HEADERS = {"User-Agent": "sourcing-agent/1.0"}

RECENT_WINDOW_HOURS = 36   # only return papers submitted in the last ~1.5 days
MAX_PAPERS = 30


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # HF returns 2026-04-30T20:00:00.000Z
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_hf_papers() -> List[Dict[str, Any]]:
    """Fetch curated trending papers from HuggingFace daily papers API."""
    try:
        resp = httpx.get(
            API_URL,
            params={"limit": MAX_PAPERS},
            headers=HEADERS,
            timeout=12,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_WINDOW_HOURS)
    candidates: List[Dict[str, Any]] = []

    for entry in data:
        paper = entry.get("paper") or {}
        title = paper.get("title") or entry.get("title") or ""
        title = title.replace("\n", " ").strip()
        if not title:
            continue

        paper_id = paper.get("id") or ""
        if not paper_id:
            continue
        url = f"https://huggingface.co/papers/{paper_id}"

        # Recency cutoff: HF curators decide WHEN a paper hits the daily list
        # (`submittedOnDailyAt`) — that's the freshness signal we care about,
        # NOT the paper's original arxiv publish date which may be days old.
        submitted_at_str = (
            paper.get("submittedOnDailyAt")
            or entry.get("publishedAt")
            or paper.get("publishedAt")
        )
        submitted_at = _parse_iso(submitted_at_str)
        if submitted_at and submitted_at < cutoff:
            continue

        upvotes = int(paper.get("upvotes", 0) or 0)
        num_comments = int(entry.get("numComments", 0) or 0)
        # Treat HF community engagement as virality signal (upvotes + comments)
        virality_signal = upvotes * 3 + num_comments

        ai_summary = paper.get("ai_summary") or paper.get("summary") or ""

        candidates.append({
            "title": title,
            "url": url,
            "source_name": "HuggingFace Daily Papers",
            "source_weight": 0.95,
            "official": False,
            "published_at": submitted_at_str,
            "virality_signal": virality_signal,
            "content_bias": "educational",
            "raw_text": ai_summary[:1200],
            "thumbnail_url": entry.get("thumbnail"),
        })

    return candidates
