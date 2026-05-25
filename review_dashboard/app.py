"""
review_dashboard — Phase 3.5 Human-in-the-Loop Review Interface
================================================================
Two tabs:
  Queue     → pending topics (approved=null). Approve triggers Phase 4.
  Inventory → 10-day rolling window. Approved posts, rejected topics, Posted toggle.

Run:
  python -m review_dashboard.app          # via console script
  uvicorn review_dashboard.app:app        # raw uvicorn
"""

import json
import logging
import re
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CONTENT_GEN = BASE_DIR.parent

SOURCING_OUTPUTS = CONTENT_GEN / "sourcing_agent" / "outputs"
REMOTION_RESULTS = CONTENT_GEN / "remotion_dev" / "results" / "textposts"
REMOTION_VIDEOS_DIR = CONTENT_GEN / "remotion_dev" / "outputs" / "videos"
FEEDBACK_FILE = CONTENT_GEN / "sourcing_agent" / "feedback.json"
SCRIPT_AGENT_DIR = CONTENT_GEN / "script_agent"
SCRIPT_AGENT_LOGS = SCRIPT_AGENT_DIR / "logs"

# Keywords for smart redo routing
_FULL_KW = {
    "narration", "voiceover", "story", "tone", "long", "short", "boring",
    "pacing", "script", "rewrite", "redo", "energy", "voice", "words",
}
_SCENE_KW = {
    "image", "scene", "picture", "photo", "layout", "visual", "screenshot",
    "replace", "wrong", "graphic", "background", "clip",
}
_RENDER_KW = {
    "font", "color", "colour", "caption", "subtitle", "timing", "render",
    "size", "cut", "transition",
}

load_dotenv(CONTENT_GEN / "sourcing_agent" / ".env")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000")

app = FastAPI(title="Content Review Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
if REMOTION_VIDEOS_DIR.exists():
    app.mount(
        "/rendered-videos",
        StaticFiles(directory=REMOTION_VIDEOS_DIR),
        name="rendered-videos",
    )
templates = Jinja2Templates(directory=BASE_DIR / "templates")

RETENTION_DAYS = 10


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load_topic(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path) as f:
            data = json.load(f)
        data["_path"] = str(path)
        data["_slug"] = path.parent.name
        return data
    except Exception:
        return None


def _save_topic(path: Path, data: Dict[str, Any]):
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    with open(path, "w") as f:
        json.dump(clean, f, indent=2, default=str)


def _all_topics(max_days: int = RETENTION_DAYS) -> List[Dict[str, Any]]:
    """
    Return all topic.json files within the rolling window.
    Skips _legacy/ folder so archived flat-format topics don't pollute the dashboard.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    topics = []
    if not SOURCING_OUTPUTS.exists():
        return topics
    for topic_file in SOURCING_OUTPUTS.rglob("topic.json"):
        if "_legacy" in topic_file.parts:
            continue
        data = _load_topic(topic_file)
        if not data:
            continue
        pub = data.get("published_at") or data.get("_mtime")
        if pub:
            try:
                dt = datetime.fromisoformat(str(pub)).replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                pass
        topics.append(data)
    return topics


def _pending_topics() -> List[Dict[str, Any]]:
    """Topics not yet reviewed (approved=null)."""
    topics = [t for t in _all_topics(max_days=7) if t.get("approved") is None]
    return sorted(topics, key=lambda x: x.get("score", 0), reverse=True)


def _pending_topics_grouped() -> Dict[str, List[Dict[str, Any]]]:
    """Pending topics grouped by published_at date (newest first), sorted by score."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for t in _pending_topics():
        pub = t.get("published_at") or ""
        try:
            key = datetime.fromisoformat(str(pub).replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            key = "0000-00-00"
        grouped.setdefault(key, []).append(t)
    for k in grouped:
        grouped[k].sort(key=lambda x: x.get("score", 0), reverse=True)
    return dict(sorted(grouped.items(), reverse=True))


def _video_http_url(abs_path: str) -> Optional[str]:
    """Convert an absolute video_path to a /rendered-videos/... HTTP URL."""
    if not abs_path:
        return None
    try:
        p = Path(abs_path)
        rel = p.relative_to(REMOTION_VIDEOS_DIR)
        return f"/rendered-videos/{str(rel).replace(os.sep, '/')}"
    except ValueError:
        return None


def _route_redo_feedback(feedback: str) -> str:
    """
    Classify feedback text into a pipeline stage:
      'full'   → redo narration + scenes + render
      'scenes' → reuse narrative, redo scenes + render
      'render' → reuse script, redo render only
    Uses keyword fast-path; falls back to a Claude mini-call for ambiguous text.
    """
    low = feedback.lower()
    words = set(re.findall(r"\w+", low))
    full_hits = len(words & _FULL_KW)
    scene_hits = len(words & _SCENE_KW)
    render_hits = len(words & _RENDER_KW)

    # Clear winner — no API call needed
    best = max(full_hits, scene_hits, render_hits)
    if best > 0:
        if full_hits == best:
            return "full"
        if scene_hits == best:
            return "scenes"
        return "render"

    # Ambiguous — ask Claude haiku for a one-word classification
    try:
        import anthropic as _ant
        client = _ant.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=5,
            messages=[{
                "role": "user",
                "content": (
                    "Classify this video-editing feedback as exactly one of: "
                    "'full' (redo narration+scenes+render), "
                    "'scenes' (redo scenes+render only), "
                    "'render' (redo render only). "
                    f"Feedback: {feedback!r}. Reply with one word only."
                ),
            }],
        )
        stage = msg.content[0].text.strip().lower().split()[0]
        if stage in ("full", "scenes", "render"):
            return stage
    except Exception:
        pass
    return "full"  # safe default


def _inventory_topics() -> Dict[str, List[Dict[str, Any]]]:
    """
    Approved topics for the last 10 days, enriched with video URLs, grouped by
    date (newest first). Only topics that went through Queue → Approve are shown.
    """
    topics = [t for t in _all_topics() if t.get("approved") is True]

    # Enrich each topic with video URL + readiness flag
    for t in topics:
        vp = t.get("video_path") or ""
        url = _video_http_url(vp)
        t["_video_url"] = url
        # Video is ready when the file actually exists and is non-empty
        t["_video_ready"] = (
            bool(vp)
            and Path(vp).exists()
            and Path(vp).stat().st_size > 1000
        )

    # Group by ISO date (for correct sort) but store display label alongside
    # Key → {"label": str, "sort_key": str, "items": [...]}
    buckets: Dict[str, Dict] = {}
    for t in topics:
        pub = t.get("published_at", "")
        try:
            dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
            sort_key = dt.strftime("%Y-%m-%d")
            label = dt.strftime("%A, %B %-d %Y")
        except Exception:
            sort_key = "0000-00-00"
            label = "Unknown Date"
        if sort_key not in buckets:
            buckets[sort_key] = {"label": label, "items": []}
        buckets[sort_key]["items"].append(t)

    for b in buckets.values():
        b["items"].sort(key=lambda x: x.get("score", 0), reverse=True)

    # Newest date at top
    return {
        buckets[k]["label"]: buckets[k]["items"]
        for k in sorted(buckets.keys(), reverse=True)
    }


def _find_post_json(slug: str) -> Optional[Dict[str, Any]]:
    """Look for Phase 4 post.json output for this slug."""
    if REMOTION_RESULTS.exists():
        for p in REMOTION_RESULTS.rglob(f"{slug}/post.json"):
            try:
                with open(p) as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def _topic_path(slug: str) -> Optional[Path]:
    """
    Find the topic.json for a given slug.
    Searches the new nested date/time structure, falling back to flat layout.
    """
    if not SOURCING_OUTPUTS.exists():
        return None
    # Try direct flat path first (back-compat)
    flat = SOURCING_OUTPUTS / slug / "topic.json"
    if flat.exists():
        return flat
    # Search nested: outputs/<date>/<time>/<slug>/topic.json
    for match in SOURCING_OUTPUTS.rglob(f"{slug}/topic.json"):
        if "_legacy" in match.parts:
            continue
        return match
    return None


def _clean_title(title: str) -> str:
    return re.sub(r"^\[.*?\]\s*", "", title).strip()


def _source_display(sources: List[Dict]) -> List[str]:
    seen = set()
    names = []
    for s in sources:
        n = s.get("name", "")
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    return names


# ── Feedback helpers ──────────────────────────────────────────────────────────

def _load_feedback() -> Dict[str, List]:
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"approved_posted": [], "rejected": []}


def _save_feedback(data: Dict):
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Template filters ──────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 85:
        return "emerald"
    if score >= 70:
        return "yellow"
    return "orange"


def score_bar_width(val: int) -> int:
    return max(2, min(100, val))


def _regex_replace(s: str, pattern: str, repl: str) -> str:
    import re as _re
    return _re.sub(pattern, repl, str(s))


def time_ago(value: str) -> str:
    """Render a published_at ISO timestamp as a relative label like '2h ago' or 'Apr 30'."""
    if not value:
        return "—"
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        secs = delta.total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        if secs < 604800:
            return f"{int(secs // 86400)}d ago"
        return dt.strftime("%b %-d")
    except Exception:
        return str(value)[:10]


def date_label(value: str) -> str:
    """Format an ISO date as 'Sunday, May 3' for Queue date bars."""
    if not value:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d")
    except Exception:
        return str(value)[:10]


templates.env.filters["score_color"] = score_color
templates.env.filters["score_bar_width"] = score_bar_width
templates.env.filters["clean_title"] = _clean_title
templates.env.filters["regex_replace"] = _regex_replace
templates.env.filters["time_ago"] = time_ago
templates.env.filters["date_label"] = date_label


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def queue_tab(request: Request):
    topics = _pending_topics()
    grouped = _pending_topics_grouped()
    return templates.TemplateResponse(
        request=request,
        name="queue.html",
        context={
            "topics": topics,
            "grouped": grouped,
            "active_tab": "queue",
            "dashboard_url": DASHBOARD_URL,
        },
    )


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_tab(request: Request):
    grouped = _inventory_topics()
    for date_group in grouped.values():
        for t in date_group:
            t["_post"] = _find_post_json(t.get("_slug", ""))
    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={"grouped": grouped, "active_tab": "inventory", "dashboard_url": DASHBOARD_URL},
    )


# ── API: Video Approve ────────────────────────────────────────────────────────

@app.post("/video-approve/{slug}", response_class=HTMLResponse)
async def video_approve(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")
    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["video_approved"] = True
    data["video_approved_at"] = datetime.now(timezone.utc).isoformat()
    _save_topic(path, data)

    # Record in feedback for sourcing learning
    feedback = _load_feedback()
    entry = {
        "slug": slug,
        "title": data.get("topic", ""),
        "content_type": data.get("content_type", ""),
        "score": data.get("score", 0),
        "sources": [s.get("name", "") for s in data.get("sources", [])[:5]],
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    feedback["approved_posted"] = [e for e in feedback.get("approved_posted", []) if e.get("slug") != slug]
    feedback["approved_posted"].append(entry)
    _save_feedback(feedback)

    title = _clean_title(data.get("topic", slug))
    return HTMLResponse(content=f"""
<div id="video-card-{slug}" class="flex flex-col rounded-2xl overflow-hidden shadow-card ring-2 ring-emerald-400 bg-white">
  <div class="bg-emerald-50 px-4 py-3 flex items-center gap-2 border-b border-emerald-100">
    <span class="text-lg">✓</span>
    <span class="text-emerald-800 font-semibold text-sm">Approved — queued for posting</span>
  </div>
  <div class="p-4">
    <p class="text-sm text-ink-700 leading-snug line-clamp-2">{title}</p>
    <p class="text-xs text-ink-400 mt-1">Social media posting will be triggered once integrations are connected.</p>
  </div>
</div>""")


# ── API: Video Reject ─────────────────────────────────────────────────────────

@app.post("/video-reject/{slug}", response_class=HTMLResponse)
async def video_reject(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")
    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["video_rejected"] = True
    data["video_rejected_at"] = datetime.now(timezone.utc).isoformat()
    _save_topic(path, data)

    # Record rejection
    feedback = _load_feedback()
    entry = {
        "slug": slug,
        "title": data.get("topic", ""),
        "content_type": data.get("content_type", ""),
        "score": data.get("score", 0),
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    }
    feedback["rejected"] = [e for e in feedback.get("rejected", []) if e.get("slug") != slug]
    feedback["rejected"].append(entry)
    _save_feedback(feedback)

    title = _clean_title(data.get("topic", slug))
    return HTMLResponse(content=f"""
<div id="video-card-{slug}" class="flex flex-col rounded-2xl overflow-hidden opacity-50 ring-1 ring-red-200 bg-white">
  <div class="bg-red-50 px-4 py-3 flex items-center gap-2 border-b border-red-100">
    <span class="text-lg">✕</span>
    <span class="text-red-700 font-semibold text-sm">Rejected</span>
  </div>
  <div class="p-4">
    <p class="text-sm text-ink-500 line-clamp-2">{title}</p>
  </div>
</div>""")


# ── API: Video Redo ───────────────────────────────────────────────────────────

@app.post("/video-redo/{slug}", response_class=HTMLResponse)
async def video_redo(slug: str, request: Request):
    form = await request.form()
    feedback_text = (form.get("feedback") or "").strip()

    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")
    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    stage = _route_redo_feedback(feedback_text) if feedback_text else "full"

    data["redo_feedback"] = feedback_text
    data["redo_stage"] = stage
    data["redo_at"] = datetime.now(timezone.utc).isoformat()
    data["video_ready"] = False
    data["video_status"] = "regenerating"
    # Keep video_approved/video_rejected cleared for this new run
    data.pop("video_approved", None)
    data.pop("video_rejected", None)
    _save_topic(path, data)

    pid = _spawn_script_agent(path, stage=stage, feedback=feedback_text)

    title = _clean_title(data.get("topic", slug))
    stage_label = {
        "full": "narration + scenes + render",
        "scenes": "scenes + render",
        "render": "render only",
    }.get(stage, stage)
    feedback_short = (feedback_text[:90] + "…") if len(feedback_text) > 90 else feedback_text
    pid_note = f"pid {pid}" if pid else "spawn failed"
    return HTMLResponse(content=f"""
<div id="video-card-{slug}" class="flex flex-col rounded-2xl overflow-hidden shadow-card ring-1 ring-amber-300 bg-amber-50">
  <div class="px-4 py-3 flex items-center gap-2 border-b border-amber-200">
    <span class="text-amber-600 text-lg animate-spin inline-block">⟳</span>
    <span class="text-amber-900 font-semibold text-sm">Regenerating…</span>
    <span class="ml-auto text-amber-600 text-xs">{stage_label}</span>
  </div>
  <div class="p-4">
    <p class="text-sm font-medium text-ink-800 line-clamp-1 mb-1">{title}</p>
    <p class="text-xs text-ink-500 italic line-clamp-2">"{feedback_short}"</p>
    <p class="text-[10px] text-ink-400 mt-2">{pid_note} · <a href="/inventory" class="underline">refresh to check</a></p>
  </div>
</div>""")


# ── API: Approve ──────────────────────────────────────────────────────────────

def _spawn_script_agent(
    topic_path: Path,
    stage: str = "full",
    feedback: str = "",
) -> Optional[int]:
    """
    Fire the script_agent package as a detached background subprocess.

    Invoked as `python -m script_agent` from the repo root so Python
    resolves the package context for relative imports. Pipeline output
    streams to script_agent/logs/<slug>-<HHMMSS>.log. Returns the PID,
    or None if spawn failed.
    """
    SCRIPT_AGENT_LOGS.mkdir(parents=True, exist_ok=True)
    slug = topic_path.parent.name
    log_path = SCRIPT_AGENT_LOGS / f"{slug}-{datetime.now().strftime('%H%M%S')}.log"

    cmd = [sys.executable, "-m", "script_agent", "--topic", str(topic_path.resolve())]
    if stage != "full":
        cmd += ["--stage", stage]
    if feedback:
        cmd += ["--feedback", feedback]

    try:
        log_file = open(log_path, "w")  # noqa: SIM115 — kept open for the child
        proc = subprocess.Popen(
            cmd,
            cwd=CONTENT_GEN,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log.info(
            "🚀 script_agent spawned for %s (stage=%s, pid=%d, log=%s)",
            slug, stage, proc.pid, log_path,
        )
        return proc.pid
    except Exception as exc:
        log.exception("Failed to spawn script_agent for %s: %s", slug, exc)
        return None


@app.post("/approve/{slug}", response_class=HTMLResponse)
async def approve_topic(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")

    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["approved"] = True
    data["video_status"] = "generating"
    _save_topic(path, data)

    # Touch a phase4.ready flag (script_agent will consume it)
    (path.parent / "phase4.ready").touch()

    # Fire the script_agent pipeline asynchronously
    pid = _spawn_script_agent(path)
    if pid is None:
        log.warning("script_agent spawn failed for %s — phase4.ready flag remains", slug)

    return HTMLResponse(content=_approved_card_html(slug, data))


# ── API: Reject ───────────────────────────────────────────────────────────────

@app.post("/reject/{slug}", response_class=HTMLResponse)
async def reject_topic(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")

    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["approved"] = False
    _save_topic(path, data)

    # Record rejection in feedback.json for score.py to learn from
    feedback = _load_feedback()
    entry = {
        "slug": slug,
        "title": data.get("topic", ""),
        "content_type": data.get("content_type", ""),
        "score": data.get("score", 0),
        "sources": [s.get("name", "") for s in data.get("sources", [])[:5]],
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    }
    feedback["rejected"] = [
        e for e in feedback["rejected"] if e.get("slug") != slug
    ]
    feedback["rejected"].append(entry)
    _save_feedback(feedback)

    return HTMLResponse(content=_rejected_card_html(slug, data))


# ── API: Mark posted ──────────────────────────────────────────────────────────

@app.post("/mark-posted/{slug}", response_class=HTMLResponse)
async def mark_posted(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")

    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["already_posted"] = True
    _save_topic(path, data)

    # Record in feedback.json so score.py can boost similar sources
    feedback = _load_feedback()
    entry = {
        "slug": slug,
        "title": data.get("topic", ""),
        "content_type": data.get("content_type", ""),
        "score": data.get("score", 0),
        "sources": [s.get("name", "") for s in data.get("sources", [])[:5]],
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    feedback["approved_posted"] = [
        e for e in feedback["approved_posted"] if e.get("slug") != slug
    ]
    feedback["approved_posted"].append(entry)
    _save_feedback(feedback)

    return HTMLResponse(content=_posted_badge_html(slug))


# ── API: Mark unposted (undo) ─────────────────────────────────────────────────

@app.post("/unmark-posted/{slug}", response_class=HTMLResponse)
async def unmark_posted(slug: str, request: Request):
    path = _topic_path(slug)
    if not path:
        raise HTTPException(status_code=404, detail="Topic not found")

    data = _load_topic(path)
    if not data:
        raise HTTPException(status_code=500, detail="Could not read topic")

    data["already_posted"] = False
    _save_topic(path, data)

    feedback = _load_feedback()
    feedback["approved_posted"] = [
        e for e in feedback["approved_posted"] if e.get("slug") != slug
    ]
    _save_feedback(feedback)

    return HTMLResponse(content=_unposted_badge_html(slug))


# ── Inline HTML fragments (HTMX responses) ────────────────────────────────────

def _approved_card_html(slug: str, data: Dict) -> str:
    title = _clean_title(data.get("topic", slug))
    score = data.get("score", 0)
    return f"""
<div id="card-{slug}" class="bg-white rounded-2xl shadow-soft p-6 flex items-center gap-4 ring-1 ring-emerald-100">
  <span class="inline-flex items-center justify-center h-9 w-9 rounded-full bg-sage-soft text-emerald-900 font-semibold text-sm shrink-0">✓</span>
  <div class="flex-1 min-w-0">
    <p class="font-semibold text-ink-900 leading-snug line-clamp-1">{title}</p>
    <p class="text-xs text-ink-500 mt-1">Approved · score {score} · <span class="text-ink-700">Phase 4 queued</span></p>
  </div>
</div>"""


def _rejected_card_html(slug: str, data: Dict) -> str:
    title = _clean_title(data.get("topic", slug))
    score = data.get("score", 0)
    return f"""
<div id="card-{slug}" class="bg-cream-100 rounded-2xl border border-cream-300 p-6 flex items-center gap-4 opacity-75">
  <span class="inline-flex items-center justify-center h-9 w-9 rounded-full bg-peach-soft text-orange-900 font-semibold text-sm shrink-0">×</span>
  <div class="flex-1 min-w-0">
    <p class="font-semibold text-ink-700 leading-snug line-clamp-1">{title}</p>
    <p class="text-xs text-ink-500 mt-1">Rejected · score {score} · <span class="text-ink-600">moved to inventory</span></p>
  </div>
</div>"""


def _posted_badge_html(slug: str) -> str:
    return f"""
<div id="posted-toggle-{slug}" class="text-right">
  <span class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">
    ✓ Posted
  </span>
  <button hx-post="/unmark-posted/{slug}" hx-target="#posted-toggle-{slug}" hx-swap="outerHTML"
    class="block text-[11px] text-ink-500 hover:text-ink-900 underline underline-offset-2 mt-1.5 ml-auto">undo</button>
</div>"""


def _unposted_badge_html(slug: str) -> str:
    return f"""
<div id="posted-toggle-{slug}">
  <button hx-post="/mark-posted/{slug}" hx-target="#posted-toggle-{slug}" hx-swap="outerHTML"
    class="rounded-full bg-cream-100 hover:bg-cream-200 border border-cream-400 px-4 py-2 text-xs font-medium text-ink-700 transition-colors whitespace-nowrap">
    Mark posted
  </button>
</div>"""


def run() -> None:
    """Console-script entry point: launch uvicorn on PORT (default 8000)."""
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    reload_flag = os.environ.get("RELOAD", "false").lower() == "true"
    uvicorn.run("review_dashboard.app:app", host=host, port=port, reload=reload_flag)


if __name__ == "__main__":
    run()
