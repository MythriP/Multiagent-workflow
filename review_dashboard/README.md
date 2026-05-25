# review_dashboard

Human-in-the-loop FastAPI app for reviewing sourced topics and rendered videos.

## Two tabs

- **Queue** — pending topics (`approved=null`). Approve triggers `script_agent`.
- **Inventory** — 10-day rolling window of approved/rejected items with a `Posted` toggle.

## Install

```bash
pip install -e .
```

## Run

```bash
python -m review_dashboard.app          # http://localhost:8000
```

Environment knobs:

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | listen port |
| `HOST` | `127.0.0.1` | bind host |
| `RELOAD` | `false` | enable uvicorn auto-reload (dev) |
| `DASHBOARD_URL` | `http://localhost:8000` | absolute URL used in Slack approval links |

## Layout

```
review_dashboard/
├── __init__.py
├── app.py                  # FastAPI app + `run()` entry point
├── pyproject.toml
├── static/                 # Tailwind + HTMX assets
└── templates/              # Jinja2 templates (queue.html, inventory.html, …)
```

## Data sources

- Reads `sourcing_agent/outputs/**/topic.json`.
- Writes approval state into the topic JSON itself + `sourcing_agent/feedback.json`.
- Reads rendered videos from `remotion_dev/outputs/videos/**/final.mp4`.
- Reads logs from `script_agent/logs/`.
