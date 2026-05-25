"""
NewsAPI source — Tier 3, requires API key.
Polled every 2 hours to stay within 100 req/day free tier.
"""

import httpx
import yaml
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
NEWSAPI_BASE = "https://newsapi.org/v2/everything"

AI_DOMAINS = [
    "techcrunch.com", "theverge.com", "wired.com", "technologyreview.com",
    "venturebeat.com", "arstechnica.com", "zdnet.com", "theregister.com",
]


def fetch_newsapi(max_age_hours: int = 48) -> List[Dict[str, Any]]:
    """Fetch AI/ML news from NewsAPI."""
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        return []

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    queries = config.get("newsapi", {}).get("queries", ["artificial intelligence"])
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    candidates = []
    seen_urls: set = set()

    with httpx.Client(timeout=12) as client:
        for query in queries[:4]:  # limit to 4 queries to conserve daily budget
            try:
                resp = client.get(NEWSAPI_BASE, params={
                    "q": query,
                    "from": cutoff,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 20,
                    "apiKey": api_key,
                })
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue

            for article in data.get("articles", []):
                url = article.get("url", "").strip()
                title = article.get("title", "").strip()

                if not url or not title or url in seen_urls:
                    continue
                if "[Removed]" in title:
                    continue
                seen_urls.add(url)

                source_info = article.get("source", {})
                source_name = source_info.get("name", "NewsAPI")
                published_at = article.get("publishedAt")
                description = article.get("description") or article.get("content") or ""

                # Higher weight for known quality outlets
                domain = url.split("/")[2] if "/" in url else ""
                source_weight = 0.75 if any(d in domain for d in AI_DOMAINS) else 0.55

                candidates.append({
                    "title": title,
                    "url": url,
                    "source_name": source_name,
                    "source_weight": source_weight,
                    "official": False,
                    "published_at": published_at,
                    "virality_signal": 0,
                    "content_bias": "reactive",
                    "raw_text": description[:2000],
                })

    return candidates
