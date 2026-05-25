"""
score.py — Scores each cluster 0–100 using four signals:
  recency (0.30) + virality (0.30) + source_weight (0.20) + amplification (0.20)

Optional content_type bias boosts certain sources when --type is specified.

Feedback loop: reads sourcing_agent/feedback.json (written by review_dashboard) to
apply a -10 penalty for topics similar to recently rejected stories, and a +5 source
weight bonus for sources that have previously produced posted content.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from dateutil import parser as dateutil_parser

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ = True
except ImportError:
    _RAPIDFUZZ = False

from .classify import has_ml_depth


CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
FEEDBACK_PATH = Path(__file__).parent.parent / "feedback.json"

REJECTION_PENALTY = 10      # subtracted from score (out of 100)
PROVEN_SOURCE_BONUS = 5     # added to score for sources that yielded posted content
ML_DEPTH_BONUS = 7          # added to score for stories with ML-depth keywords in title
FEEDBACK_SIMILARITY_THRESHOLD = 72  # rapidfuzz ratio to count a topic as "similar"


def _load_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _load_feedback() -> Dict:
    if FEEDBACK_PATH.exists():
        try:
            with open(FEEDBACK_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"approved_posted": [], "rejected": []}


def _similar_to_rejected(title: str, rejected_titles: List[str]) -> bool:
    """Return True if this title is fuzzy-similar to any rejected story."""
    if not _RAPIDFUZZ or not rejected_titles:
        return False
    import re
    norm = re.sub(r"^\[.*?\]\s*", "", title.lower())
    for rej in rejected_titles:
        rej_norm = re.sub(r"^\[.*?\]\s*", "", rej.lower())
        if _fuzz.token_set_ratio(norm, rej_norm) >= FEEDBACK_SIMILARITY_THRESHOLD:
            return True
    return False


def _parse_date(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        dt = dateutil_parser.parse(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _recency_score(published_at: str | None, max_hours: int) -> float:
    """Returns 0.0–1.0, where 1.0 = just published, 0.0 = older than max_hours."""
    dt = _parse_date(published_at)
    if not dt:
        return 0.3  # unknown date: neutral
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if age_hours <= 0:
        return 1.0
    return max(0.0, 1.0 - (age_hours / max_hours))


def score_clusters(
    clusters: List[List[Dict[str, Any]]],
    content_type: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Score each cluster and return a flat list of scored story dicts, sorted
    by score descending.

    Args:
        clusters: output of cluster_candidates()
        content_type: "reactive" | "educational" | None (balanced)
    """
    cfg = _load_config()
    scoring = cfg.get("scoring", {})
    w_recency = float(scoring.get("recency_weight", 0.30))
    w_virality = float(scoring.get("virality_weight", 0.30))
    w_source = float(scoring.get("source_weight", 0.20))
    w_amp = float(scoring.get("amplification_weight", 0.20))
    max_hours = int(scoring.get("recency_max_hours", 48))

    # Load feedback from dashboard decisions
    feedback = _load_feedback()
    rejected_titles = [e.get("title", "") for e in feedback.get("rejected", [])]
    proven_sources = {
        name.lower()
        for e in feedback.get("approved_posted", [])
        for name in e.get("sources", [])
    }

    type_boosts = cfg.get("type_boosts", {})
    boost_sources = []
    boost_mult = 1.0
    if content_type and content_type in type_boosts:
        boost_sources = [s.lower() for s in type_boosts[content_type].get("sources", [])]
        boost_mult = float(type_boosts[content_type].get("boost_multiplier", 1.0))

    # Find max virality across all candidates for normalization
    all_virality = [
        c.get("virality_signal", 0)
        for cluster in clusters
        for c in cluster
    ]
    max_virality = max(all_virality) if all_virality else 1
    if max_virality == 0:
        max_virality = 1

    scored = []
    for cluster in clusters:
        # Anchor = first item (highest source_weight due to pre-sorting)
        anchor = cluster[0]

        # Best published date across cluster
        dates = [c.get("published_at") for c in cluster if c.get("published_at")]
        best_date = sorted(dates, reverse=True)[0] if dates else None

        # Recency: use best (most recent) date in cluster
        recency = _recency_score(best_date, max_hours)

        # Virality: sum of all virality signals in cluster
        total_virality = sum(c.get("virality_signal", 0) for c in cluster)
        virality = min(1.0, total_virality / max_virality)

        # Source weight: best single source in cluster
        best_source_weight = max(c.get("source_weight", 0.5) for c in cluster)

        # Amplification: distinct source names in cluster, normalized (5+ = max)
        distinct_sources = len({c.get("source_name", "") for c in cluster})
        amplification = min(1.0, distinct_sources / 5.0)

        raw_score = (
            recency * w_recency
            + virality * w_virality
            + best_source_weight * w_source
            + amplification * w_amp
        )

        # Apply content type boost
        anchor_source = anchor.get("source_name", "").lower()
        if boost_sources and any(b in anchor_source for b in boost_sources):
            raw_score = min(1.0, raw_score * boost_mult)

        score = round(raw_score * 100)

        # Feedback adjustments (applied after base score, in integer points)
        anchor_title = anchor.get("title", "")
        if _similar_to_rejected(anchor_title, rejected_titles):
            score = max(0, score - REJECTION_PENALTY)

        cluster_source_names = {c.get("source_name", "").lower() for c in cluster}
        if proven_sources and cluster_source_names & proven_sources:
            score = min(100, score + PROVEN_SOURCE_BONUS)

        # ML-depth bonus — bumps score for genuinely technical stories so
        # they outrank generic AI announcements at equal recency/virality.
        if has_ml_depth(anchor_title):
            score = min(100, score + ML_DEPTH_BONUS)

        # Determine primary content_bias from cluster
        biases = [c.get("content_bias", "both") for c in cluster]
        bias_counts = {b: biases.count(b) for b in set(biases)}
        primary_bias = max(bias_counts, key=bias_counts.get)

        scored.append({
            "_cluster": cluster,
            "_anchor": anchor,
            "title": anchor.get("title", ""),
            "primary_url": anchor.get("url", ""),
            "score": score,
            "published_at": best_date,
            "content_bias": primary_bias,
            "distinct_sources": distinct_sources,
            "recency_score": round(recency * 100),
            "virality_score": round(virality * 100),
            "source_weight_score": round(best_source_weight * 100),
            "amplification_score": round(amplification * 100),
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)
