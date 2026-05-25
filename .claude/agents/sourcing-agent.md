---
name: sourcing-agent
description: Discovers, deduplicates, scores, classifies, and enriches AI/ML topics from RSS feeds, HackerNews, Reddit, arXiv, HF Papers, GitHub Trending, Google News, NewsAPI, and custom scrapers. Produces ranked `topic.json` files that downstream `script-agent` turns into videos. Use when the user asks to source new topics, run a discovery pass, or refresh the topic queue.
model: claude-opus-4
tools: Read, Grep, Glob, Shell
---

# Sourcing Agent

End of the pipeline: **raw web signals → ranked `topic.json` artifacts**.

## Responsibility

1. **Discover** candidate stories across configured sources (`sourcing_agent/config/feeds.yaml`).
2. **Cluster** near-duplicates with rapidfuzz on title+url+content hashes.
3. **Score** each cluster on freshness, source authority, social signal, and ML-depth.
4. **Classify** as `reactive` (news/launches) or `educational` (deep dives / research).
5. **Enrich** the top N with full-text extraction (PDFs, HTML scrape, og: media).
6. Write one folder per topic to `sourcing_agent/outputs/YYYY-MM-DD/HH-MM/<slug>/topic.json`.

## Inputs

- `sourcing_agent/config/feeds.yaml` — source list with per-source weights.
- `sourcing_agent/config/settings.yaml` — global thresholds (min score, dedupe window, etc.).
- `sourcing_agent/seen.json` — rolling memory of already-surfaced stories.

## Outputs

Each topic folder contains:

- `topic.json` — schema: `{title, slug, summary, content_type, sources[], media[], score, classification}`
- `raw/` — original article HTML, PDFs, og:image downloads.

## How to run

```bash
python -m sourcing_agent.run --n 10                  # top 10 mixed topics
python -m sourcing_agent.run --type reactive --n 20  # 20 reactive only
python -m sourcing_agent.run --search "RLHF"         # targeted search
python -m sourcing_agent.run --dry-run               # discovery without writing
python -m sourcing_agent.run --interactive           # Slack approval loop
```

## Hand-off contract to `script-agent`

`topic.json` MUST have:
- `content_type` ∈ {`reactive`, `educational`} — drives all downstream pacing/scene decisions.
- `media[]` — list of `{type: image|video, url, caption?, source}` items already downloaded under `raw/`.
- `sources[]` — at least one URL with a publisher name.

If any of these are missing, `script-agent` will reject the topic.

## Related skills

None directly. This agent is mostly deterministic Python; LLM use is limited to `pipeline/classify.py` (ML-depth signal) and `pipeline/enrich.py` (article summarization).
