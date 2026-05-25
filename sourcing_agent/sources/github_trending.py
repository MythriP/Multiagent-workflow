"""
GitHub Trending source — HTML scrape of github.com/trending.
No API key needed.
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Any


TRENDING_URL = "https://github.com/trending/{lang}?since={period}&spoken_language_code=en"
LANGS = ["python", "jupyter-notebook", ""]  # empty = all languages
PERIODS = ["daily"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

AI_KEYWORDS = {
    "llm", "gpt", "ai", "ml", "model", "diffusion", "transformer", "neural",
    "inference", "embedding", "rag", "agent", "vision", "multimodal", "training",
    "finetune", "fine-tune", "language", "openai", "anthropic", "gemini", "mistral",
    "llama", "deeplearning", "deep-learning", "machine-learning",
}


def _is_ai_related(name: str, description: str) -> bool:
    text = (name + " " + description).lower()
    return any(kw in text for kw in AI_KEYWORDS)


def fetch_github_trending() -> List[Dict[str, Any]]:
    """Scrape GitHub trending repos and filter for AI/ML relevance."""
    candidates = []
    seen_urls: set = set()

    with httpx.Client(timeout=12, headers=HEADERS, follow_redirects=True) as client:
        for lang in LANGS:
            for period in PERIODS:
                try:
                    resp = client.get(TRENDING_URL.format(lang=lang, period=period))
                    resp.raise_for_status()
                except Exception:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                articles = soup.select("article.Box-row")

                for article in articles:
                    # Repo name
                    h2 = article.select_one("h2 a")
                    if not h2:
                        continue
                    repo_path = h2.get("href", "").strip().lstrip("/")
                    repo_url = f"https://github.com/{repo_path}"

                    if repo_url in seen_urls:
                        continue
                    seen_urls.add(repo_url)

                    # Description
                    desc_el = article.select_one("p")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    # Stars today
                    stars_el = article.select_one("span.d-inline-block.float-sm-right")
                    stars_today = 0
                    if stars_el:
                        txt = stars_el.get_text(strip=True).replace(",", "").split()[0]
                        try:
                            stars_today = int(txt)
                        except ValueError:
                            pass

                    # Total stars
                    star_links = article.select("a[href$='/stargazers']")
                    total_stars = 0
                    if star_links:
                        txt = star_links[0].get_text(strip=True).replace(",", "").strip()
                        try:
                            total_stars = int(txt)
                        except ValueError:
                            pass

                    repo_name = repo_path.replace("/", " / ")
                    title = f"[GitHub Trending] {repo_name}: {description[:80]}" if description else f"[GitHub Trending] {repo_name}"

                    if not _is_ai_related(repo_name, description):
                        continue

                    candidates.append({
                        "title": title,
                        "url": repo_url,
                        "source_name": "GitHub Trending",
                        "source_weight": 0.6,
                        "official": False,
                        "published_at": datetime.now(timezone.utc).isoformat(),
                        "virality_signal": stars_today * 10 + total_stars // 100,
                        "content_bias": "both",
                        "raw_text": description,
                        "github_stars_today": stars_today,
                        "github_stars_total": total_stars,
                    })

    return candidates
