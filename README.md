# Pinch — Content Generation Pipeline

A multi-agent system that turns raw AI/ML news and research into finished 9:16 vertical videos for Reels, TikTok, and YouTube Shorts.

```
                    ┌─────────────────────┐
                    │  sourcing_agent     │  RSS, HN, Reddit, arXiv, HF, GitHub,
                    │  (discover + rank)  │  Google News, NewsAPI, custom scrapers
                    └──────────┬──────────┘
                               │  topic.json
                               ▼
                    ┌─────────────────────┐
                    │  review_dashboard   │  human approve / reject / edit
                    │  (HITL, FastAPI)    │
                    └──────────┬──────────┘
                               │  approved topic
                               ▼
                    ┌─────────────────────┐
                    │  script_agent       │  vibe → narrative → voiceover →
                    │  (Claude + media)   │  scene plan → b-roll → lipsync
                    └──────────┬──────────┘
                               │  video_script.json + voiceover.mp3
                               ▼
                    ┌─────────────────────┐
                    │  remotion_dev       │  React-based render to final MP4
                    │  (TypeScript)       │
                    └─────────────────────┘
```

## Repository layout

```
content_gen/
├── .claude/                  # agent harness: agents, skills, commands, prompts
│   ├── agents/               # one .md per pipeline-stage agent
│   ├── skills/               # capabilities Claude invokes (each in its own folder)
│   ├── commands/             # slash commands (/source-topics, /generate-script, …)
│   ├── prompts/              # raw LLM prompts loaded at runtime by Python
│   └── settings.local.json
├── sourcing_agent/           # discovers + ranks topics
├── script_agent/             # turns a topic into a rendered video
├── remotion_dev/             # TypeScript/React rendering layer
├── review_dashboard/         # FastAPI HITL UI
├── training_data/            # (gitignored) videos used for in-context training
└── trainingdata_slides/      # (gitignored) reference post slides
```

## Quickstart

Each Python agent is an installable package with its own `pyproject.toml`.

```bash
# 1. Sourcing agent — discover today's top 10 AI/ML topics
cd sourcing_agent && pip install -e . && cd ..
python -m sourcing_agent --n 10

# 2. (Optional) Review dashboard — approve topics in browser
cd review_dashboard && pip install -e . && cd ..
python -m review_dashboard.app                          # http://localhost:8000

# 3. Script agent — generate a video for one approved topic
cd script_agent && pip install -e . && cd ..
python -m script_agent --topic sourcing_agent/outputs/YYYY-MM-DD/HH-MM/<slug>/topic.json

# 4. Remotion renderer (called automatically by script_agent;
#    only run manually to iterate on rendering)
cd remotion_dev && npm install
npm run dev                                             # studio at http://localhost:3000
```

## Required environment variables

Create `.env` (gitignored) at the repo root or inside each agent:

| Variable | Used by | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | script_agent, sourcing_agent | Claude calls |
| `ELEVENLABS_API_KEY` | script_agent | TTS voiceover |
| `OPENAI_API_KEY` | script_agent | image understanding |
| `FAL_KEY` | script_agent | Veo 3.1 Fast video + photoreal image + lipsync |
| `PEXELS_API_KEY` | script_agent | stock photo/video search |
| `NEWSAPI_KEY` | sourcing_agent | NewsAPI source |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | sourcing_agent | Reddit source |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | sourcing_agent | interactive approval |

## Data contracts between stages

- **`topic.json`** — output of `sourcing_agent`, input of `script_agent`. Schema documented in `.claude/agents/sourcing-agent.md`.
- **`video_script.json`** — output of `script_agent`, input of `remotion_dev`. Schema in `remotion_dev/src/video-types.ts`.

## How the agent harness works

The `.claude/` directory is read by Claude Code (and compatible runners). When you ask "source new topics and render the top one", Claude:

1. Loads the matching slash command from `.claude/commands/`.
2. Loads the relevant agent from `.claude/agents/`.
3. Auto-loads skills from `.claude/skills/` whose `description` matches the task.
4. Python pipeline code in turn loads runtime prompts from `.claude/prompts/`.

See [`.claude/README.md`](./.claude/README.md) for full details.

## Cleanup conventions

- All regeneratable artifacts (`outputs/`, `cache/`, `logs/`) are gitignored.
- Trained reference material (`training_data/`, `trainingdata_slides/`) is gitignored.
- Only the **latest** dated output folder is preserved during cleanup passes; everything older is safe to delete.

## License

Proprietary — © Pinch.
