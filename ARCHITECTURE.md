# Architecture

This document explains **how** the Pinch content pipeline works and **why** every meaningful design decision was made. If `README.md` tells you what buttons to press, this file tells you what's happening underneath.

The system has four components that talk to each other through plain JSON files on disk:

```
                    ┌────────────────────┐
                    │  sourcing_agent    │  36+ sources → rank → cluster → enrich
                    │  (Python)          │
                    └─────────┬──────────┘
                              │  topic.json
                              ▼
                    ┌────────────────────┐
                    │  review_dashboard  │  human Approve / Reject
                    │  (FastAPI + HTMX)  │  ───────► spawns script_agent on Approve
                    └─────────┬──────────┘
                              │  approved topic + phase4.ready flag
                              ▼
                    ┌────────────────────┐
                    │  script_agent      │  vibe → narrative → voiceover → scenes →
                    │  (Python)          │  media → lipsync → render
                    └─────────┬──────────┘
                              │  video_script.json + voiceover.mp3
                              ▼
                    ┌────────────────────┐
                    │  remotion_dev      │  React/TypeScript composition
                    │  (Remotion 4)      │  → video.mp4 (1080×1920 @ 30 fps)
                    └────────────────────┘
```

Every stage writes its output to `outputs/YYYY-MM-DD/HH-MM/<slug>/` so reruns never overwrite each other and you can always go back to a previous render.

---

## 1. sourcing_agent

**Job:** find the 10 most post-worthy AI/ML stories every day, score them 0–100, and enrich the winners with images, videos, and PDF figures so `script_agent` has everything it needs to make a reel.

### Data flow

```
discover_all()            →  pipeline/discover.py
   ↓
cluster_candidates()      →  pipeline/cluster.py
   ↓
score_clusters()          →  pipeline/score.py
   ↓
classify_clusters()       →  pipeline/classify.py
   ↓
Deduplicator.filter()     →  pipeline/dedupe.py
   ↓
enrich_cluster()          →  pipeline/enrich.py
   ↓
outputs/YYYY-MM-DD/HH-MM/<slug>/topic.json
```

### 1.1 Discovery — 9 source connectors

`pipeline/discover.py` fires all source modules in a thread pool (`max_workers=8`):

| Connector | What it pulls | Why we kept it |
|---|---|---|
| `sources/hackernews.py` | Front page + show HN | Best leading indicator of dev/researcher interest |
| `sources/reddit.py` | `r/MachineLearning`, `r/LocalLLaMA`, `r/singularity` | Community-vetted papers + niche releases |
| `sources/arxiv.py` | `cs.CL`, `cs.LG`, `cs.AI` recent submissions | Direct source for research papers |
| `sources/hf_papers.py` | HuggingFace Daily Papers | Curated technical papers with author commentary |
| `sources/rss_feeds.py` | 44 hand-tuned RSS feeds (`config/feeds.yaml`) | First-party lab blogs (OpenAI, DeepMind, Anthropic, etc.) — highest trust |
| `sources/github_trending.py` | GitHub trending ML repos | Catches new open-source tools before they hit news |
| `sources/google_news.py` | 17 curated query feeds (`config/settings.yaml`) | Mainstream coverage for the reactive content mix |
| `sources/newsapi.py` | 12 curated queries via NewsAPI | Backup mainstream layer (rate-limited to 100/day) |
| `sources/scrapers.py` | Site-specific scrapers for sources without RSS | Mistral, LMSYS, Anthropic press, etc. |

Every candidate normalizes to this shape:

```python
{
  "title", "url", "source_name", "source_weight",   # 0.0-1.0, from feeds.yaml
  "official",            # True = first-party lab blog
  "published_at",        # ISO timestamp
  "virality_signal",     # HN points / Reddit upvotes / 0
  "content_bias",        # "reactive" | "educational" | "both"
  "raw_text",            # for full-text similarity downstream
}
```

### 1.2 Clustering — same story, multiple sources

`pipeline/cluster.py` uses `rapidfuzz.token_set_ratio` ≥ 65 on normalized titles to bucket candidates that are the same story told from different angles. Inside each cluster we sort by `source_weight` so the highest-trust source becomes the cluster anchor.

Why fuzzy and not embedding-based? Titles are short, mostly English, and the failure mode of fuzzy match is "too lenient" (which we want — we'd rather merge two near-dupes than render two reels about the same thing). Embeddings would add a dependency and ~200 ms/run for marginal precision gain on our volumes.

### 1.3 Scoring — four signals, tunable weights

Defined in `sourcing_agent/config/settings.yaml`:

```yaml
scoring:
  recency_weight:      0.30      # 0h-old = 100, 48h+-old = 0
  virality_weight:     0.30      # sum(HN + Reddit upvotes) / max in batch
  source_weight:       0.20      # best source's tier (lab blog = 1.0)
  amplification_weight: 0.20     # distinct sources in cluster (5+ = max)
  recency_max_hours:   48
```

#### Why these weights?

- **30% recency + 30% virality (60% combined for "is this hot right now").** Short-form video has a half-life of hours. A 36-hour-old story with massive virality still feels stale by the time it ships. Equal weight stops virality from drowning out a fresh paper that hasn't had time to gather upvotes yet.
- **20% source weight.** Rewards trust without letting the OpenAI blog dominate every day's queue. The 20 % cap means a tier-1 source can still lose to a HN-trending tier-2 release.
- **20% amplification.** "Five distinct outlets covered this" is a strong "this is a real story, not press release noise" signal. Capped at 5 so a viral story doesn't snowball.

After base scoring (0–100) three feedback adjustments fire:

| Adjustment | When | Effect | Stored in |
|---|---|---|---|
| `+7 ML_DEPTH_BONUS` | Title contains technical keywords (`transformer`, `RLHF`, `MoE`, `quantization`, etc.) | Promotes real research over generic AI news | `pipeline/classify.py: has_ml_depth()` |
| `+5 PROVEN_SOURCE_BONUS` | Any source in cluster has had a previously approved post | Lets the reviewer's actual taste feed back into scoring | `sourcing_agent/feedback.json` (written by `review_dashboard`) |
| `-10 REJECTION_PENALTY` | Title is fuzzy-similar (≥72 ratio) to a previously rejected story | Stops the same dead horse from re-ranking | `sourcing_agent/feedback.json` |

The result: scoring is data-driven for the bulk of the signal but learns from human review without us having to retrain anything.

### 1.4 Classification + content mix

`pipeline/classify.py` tags each cluster as `reactive` (news, drama, launches) or `educational` (research, tutorials, technical breakdowns). The settings file enforces a daily mix:

```yaml
content_mix:
  reactive_pct: 40
  educational_pct: 60
```

This keeps the daily queue ~60% educational so the channel stays on-brand even when AI news is loud. The `--type reactive|educational` CLI flag bypasses the mix and applies a per-type source boost (1.4× / 1.45×) that biases toward known-good source lists.

### 1.5 Deduplication — across days, not just within batch

`pipeline/dedupe.py` reads `sourcing_agent/seen.json` (rolling URL set with ~30-day TTL) so a story that landed in yesterday's queue and got skipped doesn't re-rank today. `seen.json` is gitignored; it's local state, not source-of-truth.

### 1.6 Enrichment — only the winners get the expensive treatment

The first 5 steps are cheap (HTTP + string ops). Enrichment is expensive (downloads, image-decode validation, PDF parsing), so we only run it on the top N after scoring. For each winning cluster `pipeline/enrich.py` does:

1. **Image collection** — scrape the article HTML, validate every image (≥200×200, aspect ratio ≤6.0, actually decodable). Anything that looks like a logo / favicon / avatar is dropped — see `enrichment.image_min_*` in settings.
2. **Video collection** — short videos (≤10 min) are downloaded inline; long videos get up to 3 recommended start/end windows so the script agent can play just the useful segments.
3. **Document collection** — PDFs get parsed; figures get extracted (`pipeline/pdf_utils.py`, `enrich_helpers.py`).
4. **Outbound link following** — for non-paper sources we follow up to 3 high-relevance outbound links per article so the script agent has supporting context.

Output: one `topic.json` per winning cluster in `outputs/YYYY-MM-DD/HH-MM/<slug>/`, plus a `phase4.ready` flag file that `script_agent --watch` looks for.

### 1.7 Operating modes

```bash
python -m sourcing_agent              # batch: top 10 today
python -m sourcing_agent --n 20       # batch: top 20
python -m sourcing_agent --type educational
python -m sourcing_agent --search "diffusion"   # manual topic discovery
python -m sourcing_agent --watch       # daemon: poll every 30 min, Slack-alert on score > 75
python -m sourcing_agent --daily-buffer   # ensure 10 unposted topics are queued for the day
```

---

## 2. review_dashboard

**Job:** the human bottleneck. The agent doesn't post anything you haven't explicitly looked at.

### 2.1 Two tabs

- **Queue** (`/`) — pending topics where `approved=null`. Sorted by score, grouped by date. Approve / Reject / Redo buttons.
- **Inventory** (`/inventory`) — 10-day rolling window of approved items. Shows the rendered video inline (9:16 preview), plus a Posted toggle once the social integrations are wired.

### 2.2 Auto-trigger on Approve

The key behavior new contributors need to understand: **clicking Approve in the Queue tab immediately spawns `script_agent` in a detached background process**. The reviewer doesn't run anything from the terminal.

Implementation in `review_dashboard/app.py`:

```python
@app.post("/approve/{slug}")
async def approve_topic(slug: str, request: Request):
    ...
    data["approved"] = True
    data["video_status"] = "generating"
    _save_topic(path, data)
    (path.parent / "phase4.ready").touch()
    pid = _spawn_script_agent(path)        # python -m script_agent --topic <path>
    ...

def _spawn_script_agent(topic_path, stage="full", feedback=""):
    cmd = [sys.executable, "-m", "script_agent", "--topic", str(topic_path.resolve())]
    proc = subprocess.Popen(
        cmd, cwd=CONTENT_GEN,
        stdout=open(log_path, "w"), stderr=subprocess.STDOUT,
        start_new_session=True,            # detached so dashboard restart doesn't kill it
    )
    return proc.pid
```

Output streams to `script_agent/logs/<slug>-<HHMMSS>.log`. When the run finishes, `script_agent` writes `video_path` into `topic.json`, and the Inventory tab picks it up on next page load.

### 2.3 Smart redo — keyword routing, Claude fallback

`_route_redo_feedback()` classifies free-text feedback ("too long", "wrong image on the third scene", "change the font color") into a pipeline stage:

| Stage | Reuses | Re-runs | Cost |
|---|---|---|---|
| `full` | nothing | narrative + voiceover + scenes + render | full pipeline (~5-15 min, ~$0.30) |
| `scenes` | narrative + voiceover | scenes + render | ~3-8 min, ~$0.10 (no ElevenLabs) |
| `render` | scenes + voiceover | render only | ~1-2 min, ~$0 |

Three keyword sets (`_FULL_KW`, `_SCENE_KW`, `_RENDER_KW`) match the feedback text. Clear winner → no API call. Tie or zero matches → one short Claude Haiku call (`max_tokens=5`) to pick. Default fallback is `full`.

This matters because re-running narrative on every visual tweak burns ElevenLabs credits and changes the prose the user already approved. The classifier preserves locked work.

### 2.4 Feedback loop back into sourcing

Approving / rejecting a topic writes to `sourcing_agent/feedback.json` (the file that `score.py` consults — see §1.3). A "Posted" toggle on Inventory marks an item as actually published, which adds its sources to the proven-sources list for future +5 bonuses.

---

## 3. script_agent

**Job:** turn one `topic.json` into one `video.mp4`. Largest, most stage-aware component in the system.

### 3.1 The four steps

```
topic.json
   │
   ▼ vibe_planner.py           [Claude #1 — small]   → vibe.json (1 of 5 named profiles)
   │
   ▼ narrative.py              [Claude #2 — large]   → narrative_monologue.txt (pass 1)
   │                           [Claude #3 — large]   → narrative_raw.json (pass 2: beats)
   │   └── media/core.py: process_media + execute_beat_media
   │                           (images, video clips, generated, leftover, Pexels, FAL)
   │
   ▼ media/voiceover.py        [ElevenLabs]          → voiceover.mp3 + word_timestamps.json
   │
   ▼ scene_writer.py           [Claude #4 — large]   → video_script.json
   │   └── resolve_paper_walkthrough_scenes
   │   └── fix_scene_timing (word-anchored)
   │
   ▼ media/lipsync.py          [fal.ai talking-head] → lipsync-<slug>-N.mp4 (cached)
   │
   ▼ render.py → npm run render-video → DynamicReel
                                                     → video.mp4
```

### 3.2 vibe_planner — pick one of five named visual profiles

`script_agent/vibe_planner.py` defines a hand-tuned catalog of 5 vibes:

| `vibe_name` | Tone | Motion | Font style | Hook variant |
|---|---|---|---|---|
| `clean_tech_serious` | Sober research breakdown | balanced | editorial | `split_50_50` |
| `bold_statement` | Big-text manifesto | calm | neutral-sans | `split_50_50` |
| `reactive_creator` | Breaking-news energy | kinetic | kinetic-sans | `reactive_creator` |
| `moody_archive` | Investigative, archival | calm | editorial | `split_50_50` |
| `terminal_green` | Developer/sysadmin aesthetic | balanced | mono-tech | `split_50_50` |

Each vibe carries a 4-color palette, motion intensity, font choice, scene-pattern bias (which scene types to prefer), `video_gen_modifiers` (appended to every Veo prompt), and ambient backdrop queries.

**Why a curated catalog instead of LLM-composed?** Earlier we let Claude design colors + motion + font from scratch per reel. The result was inconsistent palettes (ugly color combos) and every reel felt different. Locking to 5 vibes guarantees palette harmony and a recognizable house style. The LLM only picks the name; everything downstream reads from the catalog entry. The vibe **never edits the narration** — visual concerns only.

### 3.3 narrative.py — two passes plus a critic

**Why two passes?** Earlier we asked Claude to write narration + plan visuals in one call. The model would self-censor the prose to match what it could show, and the writing got generic. Splitting forces it to write the best monologue first (no visual constraints), then segment it into beats for the visual layer.

**Pass 1 — freeform monologue** (`prompts/narrative-freeform.md`).
Input: topic + key facts + sources. Output: 180–230-word voiceover script in the chosen voice. Locked rules: no emojis, no [music] markers, no brand-name hallucinations.

**Pass 1.5 — critic** (`prompts/narrative-critic.md`, optional).
Reads pass-1 output and returns `PASS` or `IMPROVE: <one-paragraph critique>`. If `IMPROVE`, pass 1 reruns with the critique included. Stops after one improvement cycle. Cheaper than running pass 1 three times.

**Pass 2 — beat segmentation** (`prompts/narrative-beats.md`).
Input: monologue + media inventory. Output: structured beats with `beat_type`, `text` (verbatim substring of monologue), `preferred_media_url` (a real URL from inventory), `pexels_query` (fallback only), `needs_video_clip`, `statement` flag, etc.

The big design rule lives at the top of `narrative-beats.md`: **SOURCE MEDIA FIRST**. Each non-typography beat must pin `preferred_media_url` to an inventory item if any is plausibly on-topic. Across the reel, ≥60% of beats must pin a source URL. `pexels_query` is a safety net, not the default. (Earlier the LLM was treating Pexels as primary; reels felt like stock-footage commercials.)

**Narrative cache.** A small slug-keyed dict in `narrative.py` points to user-approved historical narrations. When you re-render one of those topics, the cached monologue is reused verbatim instead of re-calling Claude — the user explicitly said "I love this narration", we don't want to roll the dice on a slightly different second draft.

### 3.4 media — the source-media-first executor

`script_agent/media/core.py: execute_beat_media()` runs in two phases per beat. After §3.3 pass 2 has produced the beat plan:

**Phase 1 — LLM-driven (every beat):**

1. `preferred_media_url` → resolve to local file from `image_map` (or `video_map` thumbnail fallback)
2. `needs_video_clip` → download the demo clip via `yt-dlp`
3. `needs_generated_image` → OpenAI GPT-image-1 generation

After Phase 1, every source path that landed in any beat's `beat_media` is registered in `claimed_source_paths` so Phase 2 won't double-claim.

**Phase 2 — fallbacks (only beats still unmedia'd):**

4. **Inventory-leftover fallback** — if a beat has no media and didn't ask for a generated image, rotate in the next unclaimed source asset (skipping URLs that look like avatars / favicons / logos / icons). This is how we enforce "real article media wins" even when the LLM forgot to pin.
5. **Pexels** — only if the beat is still empty. `beat_pexels` is still populated for every beat with a query so the scene writer can use stock as a blurred ambient back-layer behind text-only overlays, but the main `beat_media` is left alone.
6. **fal.ai FLUX schnell** — last-resort photoreal still.
7. **`best_image()` final fallback** — pick any usable image we have left.

The strict ordering is intentional: each fallback should fire only when the strictly-better previous step had nothing to offer.

### 3.5 voiceover.py — ElevenLabs + word timestamps

`script_agent/media/voiceover.py` calls ElevenLabs Turbo v2.5 with the chosen voice ID (defaults to `9q7HpZwZrB0d33BmNpWh`). The response includes per-word timing — these are the source of truth that the scene writer later uses to anchor every scene's duration to actual speech.

`SKIP_VOICEOVER=true` in `.env` skips the ElevenLabs call entirely (estimates duration from word count at ~2.5 wps) for cheap visual iteration. Default for new repos is `false`.

### 3.6 scene_writer.py — Claude composes video_script.json

Reads narrative + beats + word_timestamps + media inventory + vibe and produces a `video_script.json` matching the Zod schema in `remotion_dev/src/DynamicReel.tsx`. The LLM emits one scene per beat (mostly 1:1, with `paper_walkthrough` absorbing all `beat_type=="paper"` beats).

After Claude returns, three Python post-processors run:

1. **`resolve_paper_walkthrough_scenes`** — looks up each paper-stop's `anchor_id` against the `paper_outline` (built when the source PDF was rendered), then derives that stop's `dwell_sec` from the actual voice duration of the beat it owns. Caps applied:
   - Single-stop walkthrough (1 paper beat) → ≤ 6.0 s total
   - Multi-stop → ≤ 4.0 s per stop, ≤ 14.0 s total
   
   Reason: the paper is supporting evidence, not the show. Earlier the walkthrough ate 35+ seconds of an 89-second reel.

2. **`fix_scene_timing`** — for every other scene type, recomputes `duration_sec` to exactly span the union of consumed beats' voice-window. Each scene extends to the start of the next scene's first beat so audio is fully covered with no overlap. For walkthroughs, this only ever **shrinks** the LLM-emitted duration; trailing voice spills onto the next scene rather than stretching the walkthrough past its cap.

3. **`_build_statement_segments`** — for every beat marked `statement: true`, build a kinetic-typography overlay segment. Beats longer than 14 words are skipped (they fall back to per-word `PillCaption`). Reason: the `StatementOverlay` component renders at a hero-sized font; long phrases wrap and cover the canvas.

The result is a tightly-budgeted reel: target 75–85 s, hard max 89 s, auto-trimmed proportionally if it goes over. We picked 89 s because TikTok / Reels / Shorts watch-completion drops sharply past that mark.

### 3.7 lipsync — fal.ai talking-head, aggressively cached

`script_agent/media/lipsync.py` calls fal.ai's talking-head model (default `fal-ai/bytedance/omnihuman`) for the avatar segments. Each clip is keyed by `sha1(audio + image + model_id)`. Identical inputs → instant cache hit, no fal.ai call.

**Cache directory:** `script_agent/media/.cache/lipsync/`. This is the **expensive** cache — a lipsync call is ~30–60s of wall-clock plus ~$0.10 per clip. The cache makes development iteration tolerable.

The rendered clips also get staged into `remotion_dev/public/avatar/lipsync-<slug>-N.mp4` for Remotion to pick up. We intentionally **keep those staged clips checked into git** as a second cache layer — a fresh clone of the repo gets warm cache for previously-rendered topics, so a teammate doesn't have to re-pay for fal.ai calls to re-render an existing reel. Same logic for `public/voiceover.mp3`.

### 3.8 render.py — invoke Remotion

Writes `video_script.json` next to `voiceover.mp3` in the run's output directory, copies them into `remotion_dev/public/` so Remotion's `staticFile()` can find them, then shells out:

```
npm run render-video -- /abs/path/to/video_script.json
```

Remotion bundles the React project, picks the `DynamicReel` composition, and writes `video.mp4` to `remotion_dev/outputs/videos/YYYY-MM-DD/HH-MM/<slug>/`.

### 3.9 Run stages and env-var skips

```bash
python -m script_agent --topic <path>                       # full pipeline
python -m script_agent --topic <path> --stage scenes        # reuse narrative+voiceover
python -m script_agent --topic <path> --stage render        # reuse video_script.json
python -m script_agent --topic <path> --feedback "too long" # inject into the relevant prompt
python -m script_agent --watch                              # daemon: poll sourcing_agent/outputs/ for phase4.ready
```

Cost-control env vars (defaults in `.env`):

| Var | Default | What it skips |
|---|---|---|
| `SKIP_VOICEOVER` | `false` | ElevenLabs TTS — estimates audio length from word count |
| `SKIP_LIPSYNC` | `false` | fal.ai talking-head calls — renders avatar as still image |
| `SKIP_VIDEO_GEN` | `false` | Veo 3.1 Fast text-to-video — falls back to Pexels stock |
| `MAX_VIDEO_GEN_REQUESTS` | `4` | Per-reel Veo budget |

---

## 4. remotion_dev

**Job:** render `video_script.json` to a 1080×1920 H.264 MP4 at 30 fps.

### 4.1 Why Remotion

Programmatic React/TypeScript video. The schema (`video_script.json`) is strongly typed via Zod (`src/DynamicReel.tsx`), so the Python scene writer can't emit something the renderer doesn't know how to draw. Hot-reload Studio (`npm run dev`) lets us iterate on a scene component visually with sub-second feedback before re-rendering the whole reel.

### 4.2 DynamicReel composition

`src/DynamicReel.tsx` defines:

- The Zod schema for the entire video script (vibe, scenes, statement segments, sfx track, lipsync segments, word timestamps, avatar image).
- `calcDynamicReelMetadata` which sets the render duration from the sum of scene durations (capped at 89 s).
- The scene dispatcher — a switch over `scene.type` that mounts the right `<XxxScene>` component.
- Global overlays mounted above every scene: ambient backdrop, vibe-aware dot grid, statement overlay, pill captions, avatar overlay, lipsync video segments, sfx track, grain + vignette.

### 4.3 Scene types (16 declared in DynamicReel.tsx schema)

`hook`, `split_screen`, `pipeline_highlight`, `floating_window`, `numbered_reveal`, `article_headline`, `paper_scroll`, `paper_walkthrough`, `headline`, `bar_chart`, `comparison`, `quote`, `dramatic_word`, `chat`, `cta`, `avatar_full`.

Each scene component lives in `src/scenes/`. The catalog is intentionally finite so the LLM has a small choice set and we can write strong style rules per scene type. Adding a new scene type means: (a) add a Zod variant to `DynamicReel.tsx`, (b) write the `.tsx`, (c) update `.claude/prompts/scene-writer.md` and `.claude/skills/scene-composition/SKILL.md` so the LLM knows when to pick it.

### 4.4 Legacy slide compositions

`src/templates/CoverSlide/`, `BodySlide/`, `EmbedSlide/`, `CloserSlide/`, `SlideCarousel/` and `src/compositions/AnimatedVideo.tsx` are the older "post carousel" pipeline, rendered by `scripts/render-post.ts`. They're **not wired into `script_agent`**. Kept intentionally for future text-post output; clearly labeled with a `LEGACY` comment block in `src/Root.tsx`.

---

## 5. Caching policy

| Cache | Path | Why we keep it | Invalidation |
|---|---|---|---|
| **Lipsync clips (durable)** | `script_agent/media/.cache/lipsync/` | fal.ai calls are slow (30-60s/clip) and cost ~$0.10 each. Keyed by `sha1(audio + image + model_id)` so identical re-runs are free. | Delete the directory; next run will regenerate. |
| **Lipsync clips (staged for renderer)** | `remotion_dev/public/avatar/lipsync-*.mp4` | Tracked in git so a fresh clone gets warm cache for previously-rendered topics. Saves teammates from re-paying for fal.ai. | Delete the staged file; render will rebuild on next run. |
| **Voiceover (renderer slot)** | `remotion_dev/public/voiceover.mp3` | Same idea — last-rendered voiceover sticks around so the Remotion Studio playback works without running the full pipeline. | Overwritten on every successful `script_agent` run. |
| **Pexels assets** | `script_agent/outputs/<date>/<slug>/media/pexels-*.{jpg,mp4}` | Keyed by `sha1(query + kind)` per run. | Per-run, never persists across topics. |
| **PDF rendering** | `script_agent/outputs/<date>/<slug>/_paper/paper-scroll.png` | The 1080-wide tall scroll image of the paper is expensive (PyMuPDF render). | Per-run. |
| **Source dedup** | `sourcing_agent/seen.json` | Rolling URL set so the same story doesn't re-rank tomorrow. | Auto-prunes entries older than 30 days. |
| **Per-run outputs** | `outputs/YYYY-MM-DD/HH-MM/<slug>/` everywhere | Every run goes to a fresh dated directory. Reruns are non-destructive. | Manual housekeeping; everything is gitignored. |
| **Narrative cache** | Hard-coded slug → path dict in `narrative.py` | User explicitly approved these narrations — we lock them in so re-renders don't re-roll the prose. | Edit `_NARRATIVE_CACHE` dict to add/remove entries. |

**Why some caches are tracked in git and others aren't:**
- Tracked: small, reusable across teammates, expensive to regenerate, deterministic by content hash (lipsync clips, the staged voiceover).
- Gitignored: per-topic outputs, secrets, downloaded source media, raw API responses, anything that's regenerable for ~free.

---

## 6. Data contracts

### 6.1 `topic.json` (sourcing_agent → review_dashboard → script_agent)

Key fields:

```json
{
  "topic": "Human-readable headline",
  "slug": "url-safe-id",
  "score": 87,
  "content_type": "educational",
  "content_bias": "educational",
  "published_at": "2026-05-25T08:14:00Z",
  "sources": [{"name": "arXiv", "url": "...", "weight": 1.0}],
  "media": {"images": [...], "videos": [...], "documents": [...]},
  "summary": "...",
  "key_facts": [...],

  // Written by review_dashboard:
  "approved": true,                  // null = pending, true = approved, false = rejected
  "approved_at": "...",

  // Written by script_agent on success:
  "video_status": "ready",
  "video_path": "/abs/path/to/video.mp4",
  "video_script_path": "/abs/path/to/video_script.json",
  "video_ready": true,
  "video_approved": false            // set true via Inventory "Approve Video" button
}
```

### 6.2 `video_script.json` (script_agent → remotion_dev)

Defined by `dynamicReelSchema` in `remotion_dev/src/DynamicReel.tsx`. Top-level:

```ts
{
  topic, slug, accent_color, audio_file,
  vibe,                       // VibeProfile from §3.2
  scenes: Array<Scene>,       // 16 scene variants
  statement_segments,         // kinetic-typography overlays (capped per §3.6)
  sfx_track,
  word_timestamps,            // ElevenLabs per-word timing
  lipsync_segments,           // (start_sec, end_sec, clip_src) tuples
  avatar_image,               // path under public/
}
```

The Python side validates against this schema implicitly (Remotion will throw a Zod error at render time if anything is off).

---

## 7. Design decisions, summarized

| Decision | Why |
|---|---|
| Recency 30 / virality 30 / source 20 / amplification 20 | Short-form video has hours-long half-life; we'd rather miss a viral-but-old story than ship anything stale |
| Fuzzy-match clustering (rapidfuzz ≥65) | Fast, dependency-light, fails toward "merge dupes" which is the safer mistake |
| Curated 5-vibe catalog (not LLM-composed) | Guarantees palette harmony and a recognizable house style; locks visual consistency without losing per-reel tonality |
| Two-pass narrative with optional critic | Pass 1 writes the best prose; pass 2 plans visuals. Splitting stops the LLM from neutering its own writing to fit visual constraints |
| Source-media-first (prompt rule + Python enforcement) | Stock footage makes every reel look the same. Real article media is on-brand and copyrighted to the people we're crediting |
| Paper walkthrough ≤14s total, ≤4s/stop | The paper is supporting evidence, not the show. Earlier walkthroughs ate 35+s of an 89s reel |
| Statement overlay capped at 14 words | The hero-font overlay wraps to many lines on long text and covers the canvas |
| 89-second hard reel cap | Watch-completion drops sharply past 89s on Reels/TikTok/Shorts |
| Lipsync content-hash cache (tracked + local) | fal.ai calls are slow + paid; the cache is the difference between "iterate in seconds" and "iterate in minutes" |
| Auto-spawn `script_agent` on dashboard Approve | The reviewer never opens a terminal mid-workflow — Approve is the only action that matters |
| Smart redo with keyword routing + Claude fallback | Re-running narrative on a visual tweak burns ElevenLabs credits and changes the prose the user already loved |
| Detached subprocess (`start_new_session=True`) | Restarting the dashboard mid-render doesn't kill the in-flight reel |
| Dated output directories everywhere | Reruns are non-destructive. Easy to go back to the previous render. Trivial cleanup. |

---

## 8. File map (skip if you already know the layout)

```
content_gen/
├── .claude/                 # agent harness (read by Claude Code / runner)
│   ├── agents/              # one MD per pipeline-stage agent
│   ├── skills/              # capabilities (each in its own SKILL.md folder)
│   ├── commands/            # slash commands
│   ├── prompts/             # raw LLM prompts loaded at runtime by Python
│   └── settings.local.json  # (gitignored) per-user tool allowlist
├── sourcing_agent/          # §1
├── review_dashboard/        # §2
├── script_agent/            # §3
├── remotion_dev/            # §4
├── training_data/           # (gitignored) reference videos used for in-context training
├── trainingdata_slides/     # (gitignored) reference post slides for the legacy carousel pipeline
├── README.md                # how to run it
├── ARCHITECTURE.md          # this file — how it works
└── .gitignore
```

For per-component details, see `sourcing_agent/README.md`, `script_agent/README.md`, `review_dashboard/README.md`, `remotion_dev/README.md`, and `.claude/README.md`.
