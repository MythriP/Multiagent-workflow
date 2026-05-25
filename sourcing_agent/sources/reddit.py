"""
Reddit source — JSON API, no key needed (requires User-Agent header).
Pulls top/hot posts from AI/ML subreddits.
"""

import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


SUBREDDITS = [
    ("MachineLearning", "educational"),
    ("LocalLLaMA", "both"),
    ("artificial", "reactive"),
]

HEADERS = {
    "User-Agent": "sourcing-agent/1.0 (content pipeline; contact via github)"
}


def fetch_reddit(max_age_hours: int = 48) -> List[Dict[str, Any]]:
    """Fetch top posts from AI/ML subreddits."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    candidates = []

    with httpx.Client(timeout=10, headers=HEADERS) as client:
        for subreddit, bias in SUBREDDITS:
            for sort in ("hot", "top"):
                try:
                    resp = client.get(
                        f"https://www.reddit.com/r/{subreddit}/{sort}.json",
                        params={"limit": 25, "t": "day"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    continue

                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    score = p.get("score", 0)
                    if score < 50:
                        continue

                    created_utc = p.get("created_utc")
                    if created_utc:
                        pub = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                        if pub < cutoff:
                            continue
                        published_at = pub.isoformat()
                    else:
                        published_at = None

                    title = p.get("title", "").strip()
                    post_url = p.get("url", "")
                    permalink = "https://reddit.com" + p.get("permalink", "")
                    num_comments = p.get("num_comments", 0)
                    is_self = p.get("is_self", False)

                    # Use the linked URL for news, Reddit permalink for discussions
                    url = post_url if not is_self and post_url else permalink

                    if not title:
                        continue

                    candidates.append({
                        "title": title,
                        "url": url,
                        "reddit_permalink": permalink,
                        "source_name": f"Reddit r/{subreddit}",
                        "source_weight": 0.45,
                        "official": False,
                        "published_at": published_at,
                        "reddit_score": score,
                        "reddit_comments": num_comments,
                        "virality_signal": score + (num_comments * 3),
                        "content_bias": bias,
                        "raw_text": p.get("selftext", "")[:2000],
                    })

    return candidates
