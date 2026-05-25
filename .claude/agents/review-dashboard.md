---
name: review-dashboard
description: Human-in-the-loop Flask app for reviewing sourced topics and rendered videos. Surfaces the `sourcing_agent` queue, lets a reviewer approve/reject/edit topics, and previews rendered videos from `script_agent/outputs/`. Use when the user wants to inspect, approve, or curate pipeline outputs through a browser.
model: claude-sonnet-4
tools: Read, Grep, Glob, Shell
---

# Review Dashboard

Flask app at `review_dashboard/`. Reads from `sourcing_agent/outputs/` and `script_agent/outputs/`; writes approval state to `sourcing_agent/feedback.json`.

## Responsibility

1. List today's sourced topics in a queue.
2. Show full `topic.json` + media attachments per row.
3. Approve / reject / edit metadata — writes back to `feedback.json`.
4. Embed playback of `final.mp4` per topic when the `script-agent` has completed.

## Run

```bash
python -m review_dashboard.app          # http://localhost:5000
```

## Static + templates

- `review_dashboard/templates/queue.html` — main queue view (Tailwind-styled).
- `review_dashboard/static/` — JS for inline edits + video playback.

## Hand-off

Reviewer approval gates which topics `script-agent --watch` will pick up.
