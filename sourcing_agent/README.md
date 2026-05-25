# sourcing_agent — Phase 3: Topic Discovery Engine

Automatically discovers, scores, and enriches the best AI/ML stories from 36+ sources. Outputs structured `topic.json` files for downstream content generation (Phase 4+).

---

## What it does

1. **Pulls** from 8 source types concurrently (RSS feeds, Hacker News, Reddit, arXiv, GitHub Trending, Google News, NewsAPI, direct scrapers).
2. **Clusters** articles about the same story using fuzzy title matching.
3. **Scores** each story 0–100 based on recency, virality, source authority, and cross-source amplification.
4. **Classifies** stories as `reactive` (breaking news) or `educational` (deep dives, research).
5. **Deduplicates** against `seen.json` so you never see the same story twice.
6. **Enriches** by fetching full text + collecting all images and videos from every source in the cluster.
7. **Outputs** one `topic.json` file per story under `outputs/<slug>/topic.json`.
8. **Alerts** you on Slack with Approve/Reject buttons for high-scoring stories in watch mode.

---

## Setup

### 1. Install dependencies

```bash
cd sourcing_agent
pip install -e .
```

### 2. Configure environment

Edit `.env`:

```env
NEWSAPI_KEY=139f832447df455eb946aded29e12c46   # already set

# For Slack alerts (optional but recommended):
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0123456789
SLACK_SIGNING_SECRET=...
SLACK_CALLBACK_PORT=3000
```

**Getting a Slack Bot Token:**
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
2. Go to **OAuth & Permissions** → Add Bot Token Scopes: `chat:write`, `chat:write.public`
3. Go to **Interactivity & Shortcuts** → Enable Interactivity → set Request URL to `http://YOUR_SERVER:3000/slack/actions`
4. Install to workspace → copy the **Bot User OAuth Token** into `.env`
5. Get Channel ID: right-click your Slack channel → View channel details → copy the ID at the bottom
6. Go to **Basic Information** → copy Signing Secret

---

## CLI Commands

### Batch mode (default)

Fetch all sources, score and enrich top N topics, save `topic.json` files.

```bash
python -m sourcing_agent                    # top 10 topics (mixed reactive + educational)
python -m sourcing_agent --n 20             # top 20 topics
python -m sourcing_agent --type reactive    # only breaking news / reactive stories
python -m sourcing_agent --type educational # only deep dives / research stories
```

---

### Dry run mode

Preview what topics would be generated without saving any files. Great for inspecting the pipeline.

```bash
python -m sourcing_agent --dry-run
python -m sourcing_agent --dry-run --n 20
python -m sourcing_agent --dry-run --type educational
```

**What it prints:**

```
╭────────────────────────────────────────────────────────╮
│              Sourcing Agent — 10 Topics                │
├───┬───────┬─────────────┬──────────────────────────────┤
│ # │ Score │ Type        │ Title                        │
├───┼───────┼─────────────┼──────────────────────────────┤
│ 1 │   94  │ reactive    │ Anthropic releases Claude 4  │
│ 2 │   88  │ educational │ How GPT-4 attention works... │
│ ...                                                    │
```

It shows: rank, score (0–100), content type, title, source names, and engagement signals (HN score, Reddit upvotes, published date).

---

### Interactive mode

Dry-run followed by manual selection of which topics to actually save.

```bash
python -m sourcing_agent --interactive
python -m sourcing_agent --interactive --n 20
python -m sourcing_agent --interactive --type reactive
```

After the dry-run table prints, you're prompted:
- Enter comma-separated numbers: `1,3,5`
- Type `all` to save everything shown
- Type `top` to save the top N (default 10)
- Type `none` to exit without saving

---

### Search mode

Manually search for topics on a specific subject. Not limited by recency — useful for educational/deep-dive content.

```bash
python -m sourcing_agent --search "transformer architecture"
python -m sourcing_agent --search "how Netflix recommends content"
python -m sourcing_agent --search "diffusion models explained"
python -m sourcing_agent --search "RLHF reinforcement learning human feedback"
```

Results are shown in the dry-run table, then you're asked whether to save them.

---

### Watch mode (daemon)

Continuously polls all sources and sends Slack alerts for new, high-scoring stories.

```bash
python -m sourcing_agent --watch                      # poll every 30 min, threshold 75
python -m sourcing_agent --watch --interval 15        # poll every 15 min
python -m sourcing_agent --watch --threshold 80       # only alert on score > 80
python -m sourcing_agent --watch --interval 10 --threshold 70
```

**Watch mode behavior:**
- Polls every `--interval` minutes (default: 30).
- Scores all new stories. Only stories with score > `--threshold` (default: 75) trigger Slack alerts.
- If more than 7 stories exceed the threshold in a single cycle, only the **top 7 by score** are alerted.
- Stories above the threshold (even if not alerted due to the top-7 cap) are added to `seen.json`.
- `topic.json` files are saved for all alerted stories.

**To run as a background daemon:**

```bash
nohup python -m sourcing_agent --watch > watch.log 2>&1 &
echo $! > watch.pid
```

To stop:
```bash
kill $(cat watch.pid)
```

---

### Daily buffer mode

Ensures at least N unposted topics are always queued. Run once per day via cron.

```bash
python -m sourcing_agent --daily-buffer          # ensure 10 unposted topics exist
python -m sourcing_agent --daily-buffer --n 15   # ensure 15 topics
```

If there are already enough unposted topics in `outputs/`, it does nothing. Otherwise it generates the difference and sends a Slack summary.

**Cron setup (run at 8am daily):**
```bash
crontab -e
# Add:
0 8 * * * cd /path/to/content_gen && python -m sourcing_agent --daily-buffer >> daily.log 2>&1
```

---

## topic.json Schema

Each saved story produces a `topic.json` at `outputs/<slug>/topic.json`:

```json
{
  "slug": "anthropic-releases-claude-4",
  "topic": "Anthropic releases Claude 4 with 200K context window",
  "score": 94,
  "content_type": "reactive",
  "published_at": "2026-05-02T14:30:00+00:00",
  "sources": [
    {
      "url": "https://www.anthropic.com/news/claude-4",
      "name": "Anthropic (official)",
      "weight": 1.0,
      "official": true,
      "text": "Today we are releasing Claude 4...",
      "hn_score": 847,
      "hn_comments": 312
    },
    {
      "url": "https://techcrunch.com/2026/05/02/anthropic-claude-4",
      "name": "TechCrunch AI",
      "weight": 0.75,
      "official": false,
      "text": "Anthropic today announced..."
    }
  ],
  "media": {
    "images": [
      "https://www.anthropic.com/images/claude-4-hero.jpg",
      "https://techcrunch.com/wp-content/uploads/2026/05/claude4.png"
    ],
    "videos": [
      "https://www.youtube.com/embed/abc123",
      "https://www.anthropic.com/assets/demo.mp4"
    ]
  },
  "key_facts": [
    "Claude 4 supports a 200,000-token context window.",
    "Anthropic achieved 94.3% on the MMLU benchmark."
  ],
  "already_posted": false,
  "approved": null,
  "_scoring_detail": {
    "recency": 98,
    "virality": 85,
    "source_weight": 100,
    "amplification": 80,
    "distinct_sources": 4
  }
}
```

**Fields:**
| Field | Description |
|---|---|
| `slug` | URL-safe identifier, also used as the folder name |
| `topic` | Primary story headline |
| `score` | 0–100 composite score |
| `content_type` | `reactive` or `educational` |
| `published_at` | ISO 8601 timestamp of the most recent source |
| `sources` | All sources that covered this story, ordered by `weight` |
| `media.images` | Up to 6 images (og:image, article images, Twitter card) |
| `media.videos` | Up to 4 videos (YouTube embeds, og:video, mp4 links) |
| `key_facts` | Auto-extracted sentences with numbers/quotes/factual signals |
| `already_posted` | Set to `true` by Phase 4 after content is generated |
| `approved` | `null` = pending Slack review, `true` = approved, `false` = rejected |

---

## Scoring Formula

```
score = (recency × 0.30) + (virality × 0.30) + (source_weight × 0.20) + (amplification × 0.20)
```

| Signal | Weight | How it's calculated |
|---|---|---|
| **Recency** | 30% | Linear decay from 0h (100) to 48h+ (0). Unknown dates = 30. |
| **Virality** | 30% | Sum of HN score + Reddit upvotes, normalized to max in current batch. |
| **Source weight** | 20% | From `config/feeds.yaml`. Official company blogs = 0.9–1.0, aggregators = 0.5–0.7. |
| **Amplification** | 20% | Distinct sources covering the same story. 5+ sources = max score. |

Content-type boosters apply a ×1.4 multiplier to stories from matching source types (e.g., arXiv stories get boosted when `--type educational`).

---

## Source Coverage

### Tier 1 — Always run, high signal

| Source | Method | Bias |
|---|---|---|
| Hacker News | Algolia API | Reactive |
| HuggingFace Blog | RSS | Both |
| Papers With Code | RSS | Educational |
| OpenAI Blog | RSS | Both |
| Google Research Blog | RSS | Educational |
| Microsoft AI Blog | RSS | Both |
| NVIDIA Blog | RSS | Both |
| AWS ML Blog | RSS | Both |
| GitHub AI Blog | RSS | Both |
| GitHub Trending | HTML scrape | Both |
| Google News (10 queries) | RSS | Reactive |
| TechCrunch AI | RSS | Reactive |

### Tier 2 — Daily, free

| Source | Method | Bias |
|---|---|---|
| Reddit r/MachineLearning | JSON API | Educational |
| Reddit r/LocalLLaMA | JSON API | Both |
| Reddit r/artificial | JSON API | Reactive |
| arXiv (cs.LG, cs.AI, cs.CV, cs.CL) | RSS | Educational |
| Import AI | RSS | Educational |
| The Gradient | RSS | Educational |
| The Sequence | RSS | Educational |
| WandB Blog | RSS | Educational |
| Product Hunt | RSS | Reactive |
| + 20 more company RSS feeds | RSS | Both |

### Tier 3 — API key required

| Source | Method | Bias |
|---|---|---|
| NewsAPI | REST API | Reactive |

### Scrapers (no RSS available)

| Company | Method | Notes |
|---|---|---|
| Anthropic | HTML scrape | `/news` + `/research` pages |
| Google DeepMind | Sitemap scrape | `deepmind.google/sitemap.xml` |
| Mistral AI | HTML scrape | `/news` page |
| Runway ML | HTML scrape | `/news` page |
| Cursor | Sitemap scrape | `cursor.com/sitemap.xml` |
| Stability AI | HTML scrape | `/news-updates` page |
| Perplexity | HTML scrape | `research.perplexity.ai` |

---

## Slack Interactive Alerts

When running `--watch`, stories above the score threshold trigger a Slack message with:

- Story title, score, type, and source list
- Published date + HN/Reddit engagement signals
- A link to the primary source
- A preview image (if available)
- ✅ **Approve** and ❌ **Reject** buttons

Clicking Approve sets `approved: true` in `topic.json` and updates the Slack message.
Clicking Reject sets `approved: false` and removes it from the queue.

The interaction callback server runs on port 3000 by default. For remote deployment, use ngrok or a VPS with a public IP.

---

## Configuration

### `config/feeds.yaml`
Defines all RSS feeds with `source_weight`, `tier`, `content_bias`, and `official` flag. Add or remove feeds here.

### `config/settings.yaml`
- Scoring weights
- Watch mode defaults (interval, threshold, max alerts)
- Daily buffer defaults
- Content mix (reactive/educational split)
- NewsAPI query list
- Google News query list

---

## File Structure

```
sourcing_agent/
├── run.py                    ← CLI entry point
├── requirements.txt
├── .env                      ← API keys (never commit)
├── .gitignore
├── seen.json                 ← Dedup tracking (auto-generated)
├── config/
│   ├── feeds.yaml            ← All RSS feed definitions
│   └── settings.yaml         ← Scoring, watch, and pipeline settings
├── sources/
│   ├── hackernews.py
│   ├── reddit.py
│   ├── arxiv.py
│   ├── rss_feeds.py
│   ├── github_trending.py
│   ├── google_news.py
│   ├── newsapi.py
│   └── scrapers.py           ← Anthropic, DeepMind, Mistral, Runway, Cursor, Stability, Perplexity
├── pipeline/
│   ├── discover.py           ← Runs all sources in parallel
│   ├── cluster.py            ← Groups same-story articles
│   ├── score.py              ← 0–100 composite scoring
│   ├── classify.py           ← reactive vs educational
│   ├── dedupe.py             ← seen.json management
│   └── enrich.py             ← Full text + images + videos
├── notifier/
│   └── slack.py              ← Slack alerts + interaction callback server
└── outputs/
    └── <slug>/
        └── topic.json        ← Phase 4 input
```

---

## Phase 3 Scope

Phase 3 is **topic discovery only**. It does not:
- Generate slide decks or videos (Phase 4)
- Write scripts or copy (Phase 4)
- Post to any social platform (Phase 5)

The `topic.json` output is the handoff to Phase 4. Phase 4 reads `already_posted: false` files and generates content based on `content_type`.
