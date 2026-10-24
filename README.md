# Source-to-Screen Multi-Agent Workflow

A four-stage multi-agent system that turns AI/ML news + research papers into finished 9:16 vertical videos for Reels, TikTok, and YouTube Shorts.

```
sourcing_agent  →  review_dashboard  →  script_agent  →  remotion_dev  →  video.mp4
   (Python)        (FastAPI, browser)     (Python)         (Remotion/TS)
```

> **For the why** — design decisions, scoring weights, caching strategy, per-component deep dives — read **[`ARCHITECTURE.md`](./ARCHITECTURE.md)**.
> This file is the run guide: copy/paste these commands and the pipeline works.

---

## 0. Prerequisites

- **macOS or Linux**
- **Python ≥ 3.10** (`python3 --version`)
- **Node.js ≥ 20** with `npm` (for Remotion)
- **ffmpeg** on `$PATH` (Remotion needs it: `brew install ffmpeg`)
- **yt-dlp** on `$PATH` (`pip install yt-dlp` or `brew install yt-dlp`)
- API keys for: **Anthropic, ElevenLabs, OpenAI, fal.ai, Pexels, NewsAPI** (see step 2.3)

---

## 1. One-time setup

```bash
# Clone and enter the repo
git clone <repo-url> content_gen
cd content_gen

# Install the three Python packages in editable mode
pip install -e ./sourcing_agent
pip install -e ./review_dashboard
pip install -e ./script_agent

# Install the Remotion renderer
cd remotion_dev && npm install && cd ..
```

### 1.1 Create the two `.env` files

The pipeline reads secrets from two files. Both are gitignored — they won't ship to GitHub.

**`sourcing_agent/.env`:**

```bash
NEWSAPI_KEY=...                 # newsapi.org
SLACK_BOT_TOKEN=...             # optional — only if you want Slack alerts
SLACK_CHANNEL_ID=C...           # optional
SLACK_SIGNING_SECRET=...        # optional
DASHBOARD_URL=http://localhost:8000
```

**`script_agent/.env`:**

```bash
CLAUDE_MODE=api
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=9q7HpZwZrB0d33BmNpWh
ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
NARRATIVE_MODEL=claude-sonnet-4-5
SCENE_WRITER_MODEL=claude-sonnet-4-5
PEXELS_API_KEY=...
FAL_KEY=...:...                 # format: <key_id>:<key_secret>
FAL_LIPSYNC_MODEL=fal-ai/bytedance/omnihuman

# Cost controls — set to true to skip during dev iteration
SKIP_VOICEOVER=false
SKIP_LIPSYNC=false
SKIP_VIDEO_GEN=false
MAX_VIDEO_GEN_REQUESTS=4
```

You're done with setup.

---

## 2. The daily workflow (this is the whole thing)

You'll have **two terminals open**: one for sourcing, one for the dashboard. The script agent runs itself when you click Approve.

### Terminal 1 — find today's topics

```bash
python -m sourcing_agent --n 10
```

This polls 36+ sources (RSS feeds, HackerNews, Reddit, arXiv, HF Daily Papers, GitHub Trending, Google News, NewsAPI, custom scrapers), scores every candidate 0–100, enriches the top 10 with images/videos/PDFs, and writes one `topic.json` per topic to:

```
sourcing_agent/outputs/<YYYY-MM-DD>/<HH-MM>/<slug>/topic.json
```

Useful variants:

```bash
python -m sourcing_agent --n 20                  # top 20 instead of 10
python -m sourcing_agent --type educational      # bias toward research papers
python -m sourcing_agent --type reactive         # bias toward breaking AI news
python -m sourcing_agent --search "diffusion"    # manual: find topics matching a keyword
python -m sourcing_agent --watch                 # daemon: poll every 30 min, Slack-alert on score > 75
python -m sourcing_agent --dry-run               # preview ranking, write nothing
```

Takes ~30–90 seconds.

### Terminal 2 — start the review dashboard

```bash
python -m review_dashboard.app
```

Then open **<http://localhost:8000>** in your browser. You'll see two tabs:

- **Queue** — every topic you sourced, grouped by date, sorted by score. Cards show the headline, score, source list, and a media preview.
- **Inventory** — the rolling 10-day window of approved topics with their rendered videos embedded inline.

### Step 3 — click Approve

On any Queue card, click **Approve**.

**That's the only action that matters.** Approving immediately spawns `script_agent` as a detached background process. You don't need to run anything else.

What happens behind the scenes when you click Approve:

```
review_dashboard
   │ writes  approved=true  +  phase4.ready  into topic.json
   │ spawns  python -m script_agent --topic <path>   (detached, survives dashboard restart)
   ▼
script_agent  (logs stream to script_agent/logs/<slug>-<HHMMSS>.log)
   1. vibe_planner    — Claude picks 1 of 5 visual profiles
   2. narrative       — 2-pass writer + critic → voiceover script + beat plan
   3. media           — source-media-first: article images, generated stills, Pexels fallback
   4. voiceover       — ElevenLabs TTS + per-word timestamps
   5. scene_writer    — Claude composes video_script.json
   6. lipsync         — fal.ai talking-head clips (cached by content hash)
   7. render          — npm run render-video → video.mp4
   ▼
remotion_dev/outputs/videos/<YYYY-MM-DD>/<HH-MM>/<slug>/video.mp4
```

End-to-end takes **~5–15 minutes** depending on lipsync, video-gen, and cache hits.

While it runs you can watch the log live:

```bash
tail -f script_agent/logs/<slug>-<HHMMSS>.log
```

### Step 4 — review the rendered video

Refresh the **Inventory** tab in the dashboard. When the video is ready (file exists and is > 1 KB) it appears embedded in the card at the right 9:16 aspect ratio. You can:

- **Approve Video** — marks it ready for posting and feeds the sources back into the scoring loop as proven.
- **Reject Video** — flags it.
- **Redo** — opens a free-text feedback box. The dashboard classifies your feedback:
  - "boring", "rewrite voiceover", "too long" → re-runs **everything**
  - "wrong image", "replace scene 3", "bad layout" → reuses narration + voiceover, redoes **scenes + render**
  - "change font color", "fix subtitle timing" → reuses script, redoes **render only**

The classifier is keyword-first, falls back to a one-token Claude Haiku call when keywords tie or miss.

### Step 5 — find the final video

```
remotion_dev/outputs/videos/<YYYY-MM-DD>/<HH-MM>/<slug>/video.mp4
```

Every run writes to a fresh dated directory. Reruns never overwrite. Easy to A/B compare.

---

## 3. Optional: manual modes (no dashboard)

You can run `script_agent` directly without going through the dashboard.

```bash
# Run the full pipeline on a specific topic.json
python -m script_agent --topic sourcing_agent/outputs/2026-05-25/05-48/<slug>/topic.json

# Resume from scenes (reuses narrative + voiceover from the previous run)
python -m script_agent --topic <path> --stage scenes

# Resume from render only (reuses video_script.json)
python -m script_agent --topic <path> --stage render

# Watch mode — daemon that polls sourcing_agent/outputs/ for phase4.ready flags
python -m script_agent --watch
```

To iterate on a Remotion scene component visually (sub-second hot reload):

```bash
cd remotion_dev && npm run dev      # opens Remotion Studio at http://localhost:3000
```

To re-render the last `video_script.json` without touching Python:

```bash
cd remotion_dev
npm run render-video -- /abs/path/to/video_script.json
```

---

## 4. Repository layout

```
content_gen/
├── .claude/                 # agent harness — agents, skills, commands, prompts
│   ├── agents/              # one .md per pipeline-stage agent
│   ├── skills/              # capabilities each in its own SKILL.md folder
│   ├── commands/            # slash commands (/source-topics, /generate-script, …)
│   ├── prompts/             # raw LLM prompts loaded at runtime by Python
│   └── settings.local.json  # (gitignored) per-user tool allowlist
├── sourcing_agent/          # discovers, scores, enriches topics
├── review_dashboard/        # FastAPI HITL UI — spawns script_agent on Approve
├── script_agent/            # turns one topic.json into one video.mp4
├── remotion_dev/            # TypeScript/React rendering layer
├── training_data/           # (gitignored) reference videos for in-context training
├── trainingdata_slides/     # (gitignored) reference post slides (legacy carousel)
├── README.md                # this file
├── ARCHITECTURE.md          # how it works + every design decision explained
└── .gitignore
```

Each component has its own README with deeper details:

- [`sourcing_agent/README.md`](./sourcing_agent/README.md)
- [`review_dashboard/README.md`](./review_dashboard/README.md)
- [`script_agent/README.md`](./script_agent/README.md)
- [`remotion_dev/README.md`](./remotion_dev/README.md)
- [`.claude/README.md`](./.claude/README.md)

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `python -m sourcing_agent` says "0 candidates" | API keys missing in `sourcing_agent/.env` | Add `NEWSAPI_KEY` (the others are optional, RSS + HN + arXiv work without keys) |
| Approve in dashboard doesn't trigger anything | `script_agent` not installed or `python` isn't the same interpreter that has it | Run `pip install -e ./script_agent` again from repo root; verify with `python -m script_agent --help` |
| `script_agent` errors with `OPENAI_API_KEY ... 401` | Stale key in `script_agent/.env` | Set a current `ANTHROPIC_API_KEY` and `CLAUDE_MODE=api`; the LLM mode controls whether we hit Anthropic or fall through to OpenAI |
| Remotion render fails with `uv_interface_addresses Unknown system error 1` | Sandbox blocking the renderer's local socket | Run the render command outside the sandbox (regular shell) |
| Dashboard renders, but Inventory video tile is blank | `video_path` in `topic.json` points to a file that doesn't exist or is < 1 KB | Check the log: `tail -100 script_agent/logs/<slug>-*.log` |
| Want to cheaply iterate on visuals without burning credits | ElevenLabs/fal.ai/Veo are pay-per-call | Set `SKIP_VOICEOVER=true SKIP_LIPSYNC=true SKIP_VIDEO_GEN=true` in `script_agent/.env` |
| Port 8000 already in use | Something else is bound | `PORT=8001 python -m review_dashboard.app` |

---

## 6. Cleanup conventions

- All regeneratable artifacts (`outputs/`, `logs/`, downloaded media) are gitignored.
- Output dirs (`sourcing_agent/outputs/`, `script_agent/outputs/`, `remotion_dev/outputs/`) use `YYYY-MM-DD/HH-MM/<slug>/` so old runs are easy to find and delete.
- Lipsync clip cache (`script_agent/media/.cache/lipsync/`) and staged talking-head clips (`remotion_dev/public/avatar/lipsync-*.mp4`) are **kept on purpose** — they're content-hashed, expensive to regenerate, and let teammates iterate without re-paying fal.ai. See `ARCHITECTURE.md` §5 for the full caching policy.

---

## License

Proprietary — All rights reserved.
