"""
Hacker News source — Algolia API, no key needed.
Returns top AI/ML stories from the past 48 hours.
"""

import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


HN_ALGOLIA = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"

QUERIES = [
    "machine learning",
    "large language model",
    "artificial intelligence",
    "GPT",
    "LLM",
    "deep learning",
    "neural network",
    "diffusion model",
    "AI model",
    "OpenAI",
    "Anthropic",
    "Google DeepMind",
]


def fetch_hackernews(max_age_hours: int = 48) -> List[Dict[str, Any]]:
    """Fetch top HN stories about AI/ML from the last `max_age_hours`."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    seen_ids: set = set()
    candidates = []

    with httpx.Client(timeout=10) as client:
        for query in QUERIES:
            try:
                resp = client.get(HN_ALGOLIA, params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{int(cutoff.timestamp())}",
                    "hitsPerPage": 20,
                })
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue

            for hit in data.get("hits", []):
                story_id = hit.get("objectID")
                if not story_id or story_id in seen_ids:
                    continue
                seen_ids.add(story_id)

                points = hit.get("points") or 0
                num_comments = hit.get("num_comments") or 0
                title = hit.get("title", "").strip()
                url = hit.get("url") or HN_ITEM_URL.format(id=story_id)
                created_ts = hit.get("created_at_i")

                if not title or points < 10:
                    continue

                published_at = (
                    datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
                    if created_ts else None
                )

                candidates.append({
                    "title": title,
                    "url": url,
                    "source_name": "Hacker News",
                    "source_weight": 0.4,
                    "official": False,
                    "published_at": published_at,
                    "hn_score": points,
                    "hn_comments": num_comments,
                    "virality_signal": points + (num_comments * 2),
                    "content_bias": "reactive",
                    "raw_text": "",
                })

    return candidates
