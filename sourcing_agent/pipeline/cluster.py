"""
cluster.py — Groups candidates about the same story together using
fuzzy title matching (rapidfuzz). Official sources anchor the cluster.
"""

import re
import yaml
from pathlib import Path
from typing import List, Dict, Any
from rapidfuzz import fuzz


CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_threshold() -> int:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("clustering", {}).get("title_similarity_threshold", 65)


def _normalize_title(title: str) -> str:
    """Lowercase, strip brackets/prefixes like [DeepMind], punctuation."""
    title = re.sub(r"^\[.*?\]\s*", "", title)
    title = re.sub(r"[^\w\s]", " ", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def cluster_candidates(candidates: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group candidates into clusters of related stories.
    Returns a list of clusters, each cluster being a list of candidate dicts.
    The first item in each cluster is the highest-weight (most official) source.
    """
    threshold = _load_threshold()
    clusters: List[List[Dict[str, Any]]] = []
    cluster_titles: List[str] = []

    # Sort by source_weight descending so official sources anchor clusters
    sorted_cands = sorted(candidates, key=lambda c: c.get("source_weight", 0), reverse=True)

    for candidate in sorted_cands:
        norm = _normalize_title(candidate.get("title", ""))
        if not norm:
            continue

        matched = False
        for i, cluster_title in enumerate(cluster_titles):
            ratio = fuzz.token_set_ratio(norm, cluster_title)
            if ratio >= threshold:
                clusters[i].append(candidate)
                matched = True
                break

        if not matched:
            clusters.append([candidate])
            cluster_titles.append(norm)

    return clusters
