"""
classify.py — Labels each scored story as "reactive" or "educational"
based on source bias, title keywords, and content_type filter.
"""

import re
from typing import List, Dict, Any


REACTIVE_KEYWORDS = {
    "release", "launch", "announce", "drops", "introduces", "unveils",
    "new model", "just dropped", "breaking", "update", "now available",
    "raises", "funding", "acqui", "partnership", "breach", "leaked",
    "beats", "surpasses", "outperforms", "benchmark",
}

EDUCATIONAL_KEYWORDS = {
    "how", "what is", "explained", "guide", "tutorial", "deep dive",
    "understanding", "introduction to", "survey", "overview",
    "paper", "research", "study", "analysis", "arxiv", "publication",
    "behind the scenes", "internals", "architecture", "mechanism",
}

# ML-depth keywords — strong signal for "engineering/research" content.
# These count as educational AND are used by score.py for a small score bonus
# so genuinely technical posts surface above generic AI news.
ML_DEPTH_KEYWORDS = {
    "transformer", "attention", "embedding", "embeddings", "tokenizer",
    "fine-tune", "fine-tuning", "finetuning", "rlhf", "dpo", "ppo", "grpo",
    "distillation", "quantization", "quantized", "moe", "mixture of experts",
    "kv cache", "kv-cache", "flash attention", "flashattention",
    "speculative decoding", "speculative", "ablation", "post-training",
    "pretraining", "pre-training", "training run", "loss function",
    "gradient", "optimizer", "adam", "sgd", "lora", "qlora", "peft",
    "diffusion", "diffusion model", "ddpm", "ddim",
    "rag", "retrieval-augmented", "vector database",
    "context window", "long context", "rope", "rotary",
    "inference", "throughput", "latency", "tokens per second",
    "scaling laws", "chinchilla", "emergent",
    "multimodal", "vision-language", "vlm", "vla",
    "agent", "tool use", "tool calling", "function calling",
    "evals", "benchmark", "leaderboard", "perplexity",
    "self-attention", "cross-attention", "sparse attention",
    "open weights", "open-weights", "open-source model",
    "reasoning", "chain-of-thought", "cot",
    "alignment", "rlaif", "constitutional ai",
}


def _classify_title(title: str, bias: str) -> str:
    """Classify a story based on title keywords + source bias."""
    title_lower = title.lower()

    reactive_hits = sum(1 for kw in REACTIVE_KEYWORDS if kw in title_lower)
    educational_hits = sum(1 for kw in EDUCATIONAL_KEYWORDS if kw in title_lower)
    # ML-depth keywords count double-weight toward educational since they
    # are the kind of technical signal we explicitly want to amplify.
    ml_depth_hits = sum(1 for kw in ML_DEPTH_KEYWORDS if kw in title_lower)
    educational_hits += ml_depth_hits * 2

    # If source has a strong bias, weight it 2:1 over keyword signals
    if bias == "reactive":
        reactive_hits += 2
    elif bias == "educational":
        educational_hits += 2

    if reactive_hits > educational_hits:
        return "reactive"
    return "educational"


def has_ml_depth(title: str) -> bool:
    """Used by score.py — returns True if a title contains ML-depth keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in ML_DEPTH_KEYWORDS)


def classify_clusters(
    scored_stories: List[Dict[str, Any]],
    content_type: str | None = None,
    reactive_pct: int = 60,
) -> List[Dict[str, Any]]:
    """
    Assign content_type to each story.
    If content_type filter is set, only return stories matching that type.
    Otherwise, aim for a reactive/educational mix.
    """
    for story in scored_stories:
        title = story.get("title", "")
        bias = story.get("content_bias", "both")
        story["content_type"] = _classify_title(title, bias)

    if content_type in ("reactive", "educational"):
        return [s for s in scored_stories if s["content_type"] == content_type]

    return scored_stories
