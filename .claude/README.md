# `.claude/` — Agent harness for the Pinch content pipeline

This directory is the single source of truth for everything Claude Code (and any other agent runner) needs to operate the multi-agent content pipeline.

```
.claude/
├── settings.local.json       # (gitignored) per-user tool allowlist
├── agents/                   # one agent per pipeline stage
│   ├── sourcing-agent.md
│   ├── script-agent.md
│   ├── review-dashboard.md
│   └── remotion-renderer.md
├── skills/                   # reusable capabilities agents invoke
│   ├── b-roll-orchestration/SKILL.md
│   ├── caption-styling/SKILL.md
│   ├── narration-critic/SKILL.md
│   ├── narration-voice/SKILL.md
│   ├── pacing-rules/SKILL.md
│   ├── scene-composition/SKILL.md
│   ├── video-director/SKILL.md
│   └── video-prompt/SKILL.md
├── commands/                 # slash commands invokable in chat
│   ├── source-topics.md
│   ├── generate-script.md
│   ├── render-video.md
│   └── review-queue.md
└── prompts/                  # raw LLM prompts loaded by Python at runtime
    ├── narrative.md
    ├── narrative-beats.md
    ├── narrative-critic.md
    ├── narrative-freeform.md
    ├── scene-writer.md
    └── vibe-planner.md
```

## Vocabulary

- **Agent** — a top-level process in the pipeline. Each `agents/*.md` has front matter (`name`, `description`, `model`, `tools`) and a body describing the agent's responsibility, inputs, outputs, run command, and which skills + prompts it relies on.
- **Skill** — a focused capability. Each `skills/<name>/SKILL.md` follows the Claude Skills schema: front matter (`name`, `description`) + body. Skills are auto-loaded when their description matches the current task.
- **Command** — a user-typed slash command (e.g. `/source-topics`). Each command is a short runbook.
- **Prompt** — a raw text/markdown file passed verbatim into an LLM API call by Python code. Resolved through `script_agent.paths.PROMPTS_DIR`.

## Adding a new agent

1. Create `agents/<name>.md` with the standard front matter.
2. List which skills the agent depends on under a `## Skills this agent invokes` section.
3. Add a slash command under `commands/` if humans should be able to trigger it.

## Adding a new skill

1. `mkdir .claude/skills/<slug>` and write `SKILL.md` with `name:` and `description:` front matter.
2. Write the description as a *retrieval prompt* — describe when this skill should be loaded.

## Adding a new prompt

1. Drop the file into `.claude/prompts/<name>.md`.
2. Load it from Python via `from script_agent.paths import PROMPTS_DIR; (PROMPTS_DIR / "name.md").read_text()`.
