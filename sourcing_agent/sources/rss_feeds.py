"""
RSS/Atom feed reader for all company and newsletter feeds defined in config/feeds.yaml.
"""

import feedparser
import httpx
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime


CONFIG_PATH = Path(__file__).parent.parent / "config" / "feeds.yaml"
HEADERS = {"User-Agent": "sourcing-agent/1.0"}


def _parse_date(entry) -> str | None:
    """Try to parse a date from a feedparser entry."""
    for attr in ("published", "updated", "created"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).isoformat()
            except Exception:
                pass
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return None


def fetch_rss_feeds() -> List[Dict[str, Any]]:
    """Fetch all feeds defined in config/feeds.yaml."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    feeds = config.get("feeds", [])
    candidates = []

    with httpx.Client(timeout=12, headers=HEADERS, follow_redirects=True) as client:
        for feed_cfg in feeds:
            url = feed_cfg.get("url", "")
            name = feed_cfg.get("name", url)
            source_weight = float(feed_cfg.get("source_weight", 0.7))
            official = bool(feed_cfg.get("official", False))
            content_bias = feed_cfg.get("content_bias", "both")

            try:
                resp = client.get(url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
            except Exception:
                continue

            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "").replace("\n", " ").strip()
                link = getattr(entry, "link", "").strip()
                summary = getattr(entry, "summary", "").replace("\n", " ").strip()

                if not title or not link:
                    continue

                published_at = _parse_date(entry)

                candidates.append({
                    "title": title,
                    "url": link,
                    "source_name": name,
                    "source_weight": source_weight,
                    "official": official,
                    "published_at": published_at,
                    "virality_signal": 0,
                    "content_bias": content_bias,
                    "raw_text": summary[:2000],
                })

    return candidates
