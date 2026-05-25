"""
discover.py — Runs all source connectors in parallel and returns a flat
list of candidate articles. All sources are treated equally at this stage.
"""

import concurrent.futures
from typing import List, Dict, Any

from ..sources.hackernews import fetch_hackernews
from ..sources.reddit import fetch_reddit
from ..sources.arxiv import fetch_arxiv
from ..sources.hf_papers import fetch_hf_papers
from ..sources.rss_feeds import fetch_rss_feeds
from ..sources.github_trending import fetch_github_trending
from ..sources.google_news import fetch_google_news
from ..sources.newsapi import fetch_newsapi
from ..sources.scrapers import fetch_scrapers


_SOURCES = [
    ("HackerNews", fetch_hackernews),
    ("Reddit", fetch_reddit),
    ("arXiv", fetch_arxiv),
    ("HF Daily Papers", fetch_hf_papers),
    ("RSS Feeds", fetch_rss_feeds),
    ("GitHub Trending", fetch_github_trending),
    ("Google News", fetch_google_news),
    ("NewsAPI", fetch_newsapi),
    ("Scrapers", fetch_scrapers),
]


def discover_all(verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Run all source connectors concurrently and return a flat list of candidates.
    Each candidate is a dict with at minimum: title, url, source_name,
    source_weight, official, published_at, virality_signal, content_bias, raw_text.
    """
    all_candidates: List[Dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fn): name for name, fn in _SOURCES}

        for future in concurrent.futures.as_completed(futures):
            source_name = futures[future]
            try:
                results = future.result()
                all_candidates.extend(results)
                if verbose:
                    print(f"  [discover] {source_name}: {len(results)} candidates")
            except Exception as e:
                if verbose:
                    print(f"  [discover] {source_name}: ERROR — {e}")

    return all_candidates
