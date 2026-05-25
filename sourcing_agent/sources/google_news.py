"""
Google News RSS source — parameterized queries for AI/ML topics and specific companies.
No key needed.
"""

import feedparser
import httpx
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime
from urllib.parse import quote


CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
GNEWS_BASE = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "sourcing-agent/1.0"}


def _gnews_url(query: str) -> str:
    return f"{GNEWS_BASE}?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


def _parse_date(entry) -> str | None:
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).isoformat()
            except Exception:
                pass
    return None


def fetch_google_news() -> List[Dict[str, Any]]:
    """Fetch Google News RSS for AI/ML queries and company-specific queries."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    queries = config.get("google_news", {}).get("queries", [])
    candidates = []
    seen_urls: set = set()

    with httpx.Client(timeout=12, headers=HEADERS, follow_redirects=True) as client:
        for query in queries:
            try:
                resp = client.get(_gnews_url(query))
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
            except Exception:
                continue

            for entry in feed.entries[:15]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()

                if not title or not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                published_at = _parse_date(entry)
                summary = getattr(entry, "summary", "").strip()

                # Determine if company-specific query (more targeted)
                is_company_query = any(
                    c in query for c in ["Anthropic", "DeepMind", "Mistral", "Runway",
                                         "Perplexity", "ElevenLabs", "Stability", "Cursor"]
                )
                source_weight = 0.65 if is_company_query else 0.55

                candidates.append({
                    "title": title,
                    "url": link,
                    "source_name": f"Google News ({query})",
                    "source_weight": source_weight,
                    "official": False,
                    "published_at": published_at,
                    "virality_signal": 0,
                    "content_bias": "reactive",
                    "raw_text": summary[:2000],
                })

    return candidates
