"""
arXiv source — RSS feeds for cs.LG, cs.AI, cs.CV, cs.CL.
No key needed. Returns latest research papers.
"""

import feedparser
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime


ARXIV_FEEDS = [
    ("https://arxiv.org/rss/cs.LG", "Machine Learning"),
    ("https://arxiv.org/rss/cs.AI", "Artificial Intelligence"),
    ("https://arxiv.org/rss/cs.CV", "Computer Vision"),
    ("https://arxiv.org/rss/cs.CL", "Computation and Language"),
    ("https://arxiv.org/rss/cs.NE", "Neural and Evolutionary Computing"),
    ("https://arxiv.org/rss/stat.ML", "Statistics — Machine Learning"),
]

HEADERS = {"User-Agent": "sourcing-agent/1.0"}


def fetch_arxiv() -> List[Dict[str, Any]]:
    """Fetch latest papers from arXiv ML/AI categories."""
    candidates = []
    seen_ids: set = set()

    for feed_url, category in ARXIV_FEEDS:
        try:
            resp = httpx.get(feed_url, headers=HEADERS, timeout=12, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception:
            continue

        for entry in feed.entries[:50]:
            arxiv_id = getattr(entry, "id", "").strip()
            if arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)

            title = getattr(entry, "title", "").replace("\n", " ").strip()
            link = getattr(entry, "link", arxiv_id)
            summary = getattr(entry, "summary", "").replace("\n", " ").strip()

            # Parse published date
            published_at = None
            if hasattr(entry, "published"):
                try:
                    published_at = parsedate_to_datetime(entry.published).isoformat()
                except Exception:
                    pass

            if not title:
                continue

            candidates.append({
                "title": f"[{category}] {title}",
                "url": link,
                "source_name": f"arXiv ({category})",
                "source_weight": 0.95,
                "official": True,
                "published_at": published_at,
                "virality_signal": 0,
                "content_bias": "educational",
                "raw_text": summary,
            })

    return candidates
