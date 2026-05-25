---
description: Run the sourcing_agent discovery pipeline to surface new AI/ML topics.
argument-hint: [--n N] [--type reactive|educational] [--search QUERY] [--dry-run] [--interactive]
---

Run the sourcing agent with the user's arguments and report the top results.

1. `cd /Users/mythri/Desktop/Pinch/content_gen`
2. `python -m sourcing_agent.run $ARGUMENTS`
3. After it completes, list the new topic folders under `sourcing_agent/outputs/$(date +%Y-%m-%d)/` and summarize each topic's title, content_type, and score in a table.
4. If `--interactive` was passed, remind the user to check Slack for approval prompts.
