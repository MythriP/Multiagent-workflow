#!/usr/bin/env python3
"""
sourcing_agent — Phase 3 Topic Discovery Engine
================================================
Discovers, scores, and enriches AI/ML topics from 36+ sources.
Outputs structured topic.json files to outputs/<slug>/.

Usage:
  python run.py                        # Batch: top 10 topics
  python run.py --n 20                 # Batch: top 20 topics
  python run.py --type reactive        # Only reactive/breaking stories
  python run.py --type educational     # Only educational/deep-dive stories
  python run.py --dry-run              # Preview ranked topics, no files written
  python run.py --interactive          # Dry-run then pick topics to save
  python run.py --search "topic"       # Manual search for educational topics
  python run.py --watch                # Daemon: poll every 30 min, Slack alerts
  python run.py --watch --interval 15  # Daemon with 15-min polling
  python run.py --watch --threshold 80 # Only alert on score > 80
  python run.py --daily-buffer         # Generate 10 unposted topics for the day
  python run.py --daily-buffer --n 15  # Generate 15 topics for the buffer
"""

import argparse
import json
import os
import sys
import time
import signal
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.prompt import Prompt, Confirm

load_dotenv(Path(__file__).parent / ".env")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:5000")

# Ensure sourcing_agent is importable
sys.path.insert(0, str(Path(__file__).parent))

from .pipeline.discover import discover_all
from .pipeline.cluster import cluster_candidates
from .pipeline.score import score_clusters
from .pipeline.classify import classify_clusters
from .pipeline.dedupe import Deduplicator
from .pipeline.enrich import enrich_cluster
from .notifier.slack import SlackNotifier, start_interaction_server

console = Console()
BASE_DIR = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"


def load_settings() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    n: int = 10,
    content_type: str | None = None,
    search_query: str | None = None,
    skip_dedupe: bool = False,
    verbose: bool = False,
) -> List[Dict[str, Any]]:
    """
    Full pipeline: discover → cluster → score → classify → dedupe.
    Returns scored, classified, deduped story list (not yet enriched).
    """
    settings = load_settings()

    with console.status("[bold cyan]Fetching from all sources...[/]"):
        candidates = discover_all(verbose=verbose)

    console.print(f"  [dim]Fetched {len(candidates)} raw candidates from all sources[/]")

    # Search mode: filter by query before clustering
    if search_query:
        q = search_query.lower()
        candidates = [
            c for c in candidates
            if q in (c.get("title") or "").lower()
            or q in (c.get("raw_text") or "").lower()
        ]
        console.print(f"  [dim]Search filter '{search_query}': {len(candidates)} matches[/]")

    with console.status("[bold cyan]Clustering stories...[/]"):
        clusters = cluster_candidates(candidates)

    console.print(f"  [dim]Formed {len(clusters)} story clusters[/]")

    with console.status("[bold cyan]Scoring clusters...[/]"):
        scored = score_clusters(clusters, content_type=content_type)

    with console.status("[bold cyan]Classifying stories...[/]"):
        classified = classify_clusters(scored, content_type=content_type)

    # Dedupe: filter out already-seen stories
    deduper = Deduplicator()
    if not skip_dedupe:
        before = len(classified)
        classified = deduper.filter_new(classified)
        console.print(f"  [dim]Dedupe: {before - len(classified)} stories skipped (already seen)[/]")

    # Apply content mix if no type filter
    if not content_type and not search_query:
        settings = load_settings()
        mix = settings.get("content_mix", {})
        reactive_pct = int(mix.get("reactive_pct", 60))
        reactive_n = max(1, round(n * reactive_pct / 100))
        educational_n = n - reactive_n

        reactive = [s for s in classified if s.get("content_type") == "reactive"][:reactive_n]
        educational = [s for s in classified if s.get("content_type") == "educational"][:educational_n]
        # Merge and re-sort
        classified = sorted(reactive + educational, key=lambda x: x["score"], reverse=True)
    
    # Attach slug before returning
    deduper2 = Deduplicator()
    for story in classified:
        story["_slug"] = deduper2.get_slug(story.get("title", ""))

    return classified[:n]


def _run_output_dir(slug: str, run_time: datetime | None = None) -> Path:
    """
    Build the date/time-organized output path for a topic.
    Format: outputs/YYYY-MM-DD/HH-MM/<slug>/
    """
    if run_time is None:
        run_time = datetime.now()
    date_str = run_time.strftime("%Y-%m-%d")
    time_str = run_time.strftime("%H-%M")
    return OUTPUTS_DIR / date_str / time_str / slug


def _ping_slack_summary(stories: List[Dict[str, Any]]) -> None:
    """
    Post a concise summary ping to #content with the dashboard link.
    Format: bell + count + reactive/educational breakdown + URL.
    Falls back gracefully when SLACK_BOT_TOKEN is missing or the API call fails.
    """
    if not stories:
        return
    notifier = SlackNotifier()
    if not notifier.enabled:
        count = len(stories)
        reactive = sum(1 for s in stories if s.get("content_type") == "reactive")
        educational = count - reactive
        console.print(
            f"[dim]  [slack] skipped (no SLACK_BOT_TOKEN) — would have sent: "
            f"🔔 {count} new topics · ⚡{reactive} reactive · 📚{educational} educational → {DASHBOARD_URL}[/]"
        )
        return
    ok = notifier.send_watch_summary(stories, dashboard_url=DASHBOARD_URL)
    count = len(stories)
    if ok:
        console.print(
            f"[green]  [slack] 🔔 {count} topic(s) pinged to channel → {DASHBOARD_URL}[/]"
        )
    else:
        console.print("[yellow]  [slack] post failed (check SLACK_BOT_TOKEN/SLACK_CHANNEL_ID)[/]")


def enrich_and_save(stories: List[Dict[str, Any]], dry_run: bool = False) -> List[Dict[str, Any]]:
    """Enrich stories and save topic.json files."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    enriched_list = []

    deduper = Deduplicator()
    run_time = datetime.now()

    for story in stories:
        slug = story.get("_slug", "unknown")
        with console.status(f"[bold green]Enriching: {story['title'][:60]}...[/]"):
            enriched = enrich_cluster(story)

        if not dry_run:
            out_dir = _run_output_dir(slug, run_time)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "topic.json"
            with open(out_file, "w") as f:
                json.dump(enriched, f, indent=2, default=str)

        enriched_list.append(enriched)

    if not dry_run:
        deduper.mark_batch(stories)

    return enriched_list


# ── Display helpers ───────────────────────────────────────────────────────────

def print_dry_run_table(stories: List[Dict[str, Any]]):
    """Print a rich table showing ranked topics."""
    table = Table(
        title=f"[bold cyan]Sourcing Agent — {len(stories)} Topics[/]",
        box=box.ROUNDED,
        show_lines=True,
        expand=True
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", style="bold magenta", width=7)
    table.add_column("Type", width=12)
    table.add_column("Title", style="cyan", ratio=4)
    table.add_column("Sources", ratio=2)
    table.add_column("Signals", ratio=2)

    type_colors = {"reactive": "yellow", "educational": "blue"}

    for i, story in enumerate(stories, 1):
        content_type = story.get("content_type", "")
        color = type_colors.get(content_type, "white")
        sources = story.get("_cluster", [])
        source_names = ", ".join(
            sorted({c.get("source_name", "") for c in sources[:3]})
        )
        signals_parts = []
        for c in sources:
            if c.get("hn_score"):
                signals_parts.append(f"HN:{c['hn_score']}")
            if c.get("reddit_score"):
                signals_parts.append(f"R:{c['reddit_score']}")
        signals = " | ".join(signals_parts[:3]) or "—"

        published = story.get("published_at", "")
        pub_str = published[:10] if published else "—"

        table.add_row(
            str(i),
            str(story.get("score", 0)),
            f"[{color}]{content_type}[/{color}]",
            story.get("title", "")[:100],
            source_names[:60],
            f"{signals} [{pub_str}]",
        )

    console.print(table)
    console.print()

    # Scoring breakdown
    console.print("[bold]Score breakdown legend:[/]")
    console.print("  [magenta]Score[/] = recency(30%) + virality(30%) + source_weight(20%) + amplification(20%)")
    console.print("  [cyan]Amplification[/] = how many distinct sources covered the same story\n")


# ── Modes ─────────────────────────────────────────────────────────────────────

def mode_batch(args, settings):
    """One-shot batch mode: fetch, score, enrich, save."""
    console.print(Panel(
        f"[bold cyan]Batch mode[/] — targeting [bold]{args.n}[/] topics"
        + (f" | type: [bold]{args.type}[/]" if args.type else ""),
        title="sourcing_agent"
    ))

    stories = run_pipeline(n=args.n, content_type=args.type)

    if not stories:
        console.print("[yellow]No new topics found. Try --type or --search, or wait for more content.[/]")
        return

    console.print(f"\n[green]Found {len(stories)} topics. Enriching...[/]\n")
    enriched = enrich_and_save(stories)

    console.print(f"\n[bold green]Done! {len(enriched)} topic.json files saved to outputs/[/]\n")
    for t in enriched:
        slug = t.get("slug", "")
        console.print(f"  outputs/{slug}/topic.json  [dim](score {t.get('score')})[/]")

    _ping_slack_summary(enriched)


def mode_dry_run(args, settings):
    """Dry run: show ranked topics without saving."""
    console.print(Panel(
        "[bold cyan]Dry run mode[/] — no files will be written",
        title="sourcing_agent"
    ))

    stories = run_pipeline(n=args.n, content_type=args.type, skip_dedupe=True)

    if not stories:
        console.print("[yellow]No topics found.[/]")
        return

    print_dry_run_table(stories)
    console.print(f"[dim]Total topics available: {len(stories)}. Run without --dry-run to save.[/]")


def mode_interactive(args, settings):
    """Interactive mode: show dry run then let user pick topics to save."""
    console.print(Panel(
        "[bold cyan]Interactive mode[/] — review and select topics to save",
        title="sourcing_agent"
    ))

    # Fetch more than N so user has options
    fetch_n = max(args.n * 2, 20)
    stories = run_pipeline(n=fetch_n, content_type=args.type)

    if not stories:
        console.print("[yellow]No new topics found.[/]")
        return

    print_dry_run_table(stories)

    console.print("[bold]Select topics to save:[/]")
    console.print("  Enter comma-separated numbers (e.g. 1,3,5)")
    console.print("  Or [bold]all[/] to save all, [bold]top[/] to save top N, [bold]none[/] to exit\n")

    selection = Prompt.ask("[bold cyan]Selection")

    if selection.lower() == "none":
        console.print("[yellow]Exited without saving.[/]")
        return
    elif selection.lower() == "all":
        selected = stories
    elif selection.lower() == "top":
        selected = stories[:args.n]
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(",")]
            selected = [stories[i] for i in indices if 0 <= i < len(stories)]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection. Exiting.[/]")
            return

    if not selected:
        console.print("[yellow]Nothing selected.[/]")
        return

    if Confirm.ask(f"\nSave {len(selected)} topic(s)?"):
        enriched = enrich_and_save(selected)
        console.print(f"\n[bold green]{len(enriched)} topic.json files saved.[/]")
        for t in enriched:
            console.print(f"  outputs/{t.get('slug', '')}/topic.json")
        _ping_slack_summary(enriched)


def mode_search(args, settings):
    """Search mode: query for specific topics (educational, not time-limited)."""
    if not args.search:
        console.print("[red]--search requires a query string.[/]")
        return

    console.print(Panel(
        f"[bold cyan]Search mode[/] — query: [bold]\"{args.search}\"[/]",
        title="sourcing_agent"
    ))

    stories = run_pipeline(
        n=args.n,
        content_type="educational",
        search_query=args.search,
        skip_dedupe=True,  # Don't dedupe for manual searches
    )

    if not stories:
        console.print(f"[yellow]No results for '{args.search}'. Try a different query.[/]")
        return

    print_dry_run_table(stories)

    if Confirm.ask(f"\nSave these {len(stories)} topic(s)?"):
        enriched = enrich_and_save(stories)
        console.print(f"\n[bold green]{len(enriched)} topic.json files saved.[/]")
        _ping_slack_summary(enriched)


def mode_watch(args, settings):
    """
    Watch/daemon mode: poll all sources every N minutes.
    Send Slack alerts for high-scoring new stories (score > threshold, top 7 max).
    """
    watch_cfg = settings.get("watch", {})
    interval = args.interval or int(watch_cfg.get("interval_minutes", 30))
    threshold = args.threshold or int(watch_cfg.get("score_threshold", 75))
    max_alerts = int(watch_cfg.get("max_alerts_per_cycle", 7))

    notifier = SlackNotifier()

    console.print(Panel(
        f"[bold cyan]Watch mode[/] — polling every [bold]{interval}[/] min "
        f"| threshold: [bold]{threshold}[/] "
        f"| Slack: [bold]{'enabled' if notifier.enabled else 'disabled'}[/]",
        title="sourcing_agent daemon"
    ))

    if notifier.enabled:
        start_interaction_server(notifier, OUTPUTS_DIR, port=notifier.callback_port)
    else:
        console.print("[yellow]  Slack not configured. Alerts will be printed to console only.[/]")
        console.print("[dim]  See .env for SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_SIGNING_SECRET[/]\n")

    cycle = 0
    deduper = Deduplicator()

    def handle_signal(sig, frame):
        console.print("\n[yellow]Watch mode interrupted. Exiting.[/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while True:
        cycle += 1
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        console.print(f"\n[bold cyan]── Cycle {cycle} — {now} ──[/]")

        # Fetch without deduping first so we can compare
        all_stories = run_pipeline(n=50, skip_dedupe=True)

        # Filter new only
        new_stories = deduper.filter_new(all_stories)
        console.print(f"  {len(new_stories)} new stories (out of {len(all_stories)} found)")

        # Apply score threshold and cap
        alertable = [s for s in new_stories if s.get("score", 0) > threshold]
        alertable = sorted(alertable, key=lambda x: x["score"], reverse=True)[:max_alerts]

        if alertable:
            console.print(f"  [bold green]{len(alertable)} stories above threshold {threshold} — saving and alerting[/]")

            enriched_batch = []
            cycle_time = datetime.now()
            for i, story in enumerate(alertable, 1):
                console.print(
                    f"  [{i}] score=[bold]{story['score']}[/] type={story.get('content_type', '')} — "
                    f"{story['title'][:80]}"
                )

                # Enrich and save
                enriched_story = enrich_cluster(story)
                slug = story.get("_slug", "")
                out_dir = _run_output_dir(slug, cycle_time)
                out_dir.mkdir(parents=True, exist_ok=True)
                with open(out_dir / "topic.json", "w") as f:
                    json.dump(enriched_story, f, indent=2, default=str)
                enriched_batch.append(enriched_story)

            # Send a single Slack summary ping with dashboard link
            if notifier.enabled:
                notifier.send_watch_summary(enriched_batch, dashboard_url=DASHBOARD_URL)
                console.print(f"  [dim]Slack summary sent → {DASHBOARD_URL}[/]")
            else:
                console.print(f"  [dim]Review at {DASHBOARD_URL}[/]")

            # Mark all alertable + non-alertable above threshold as seen
            all_above_threshold = [s for s in new_stories if s.get("score", 0) > threshold]
            deduper.mark_batch(all_above_threshold)
        else:
            console.print(f"  [dim]No stories above threshold {threshold}.[/]")

        console.print(f"  [dim]Sleeping {interval} minutes...[/]")
        time.sleep(interval * 60)


def mode_daily_buffer(args, settings):
    """
    Daily buffer mode: ensure N unposted topics are always available.
    Designed to run once per day (e.g. via cron at 8am).
    """
    batch_cfg = settings.get("daily_buffer", {})
    n = args.n or int(batch_cfg.get("default_n", 10))

    console.print(Panel(
        f"[bold cyan]Daily buffer mode[/] — ensuring [bold]{n}[/] unposted topics are ready",
        title="sourcing_agent"
    ))

    # Count existing unposted topics (skip archived _legacy/ folder)
    existing_unposted = []
    for topic_file in OUTPUTS_DIR.rglob("topic.json"):
        if "_legacy" in topic_file.parts:
            continue
        try:
            with open(topic_file) as f:
                data = json.load(f)
            if not data.get("already_posted") and data.get("approved") is not False:
                existing_unposted.append(data)
        except Exception:
            pass

    console.print(f"  Found {len(existing_unposted)} unposted topics already in outputs/")

    needed = max(0, n - len(existing_unposted))
    if needed == 0:
        console.print(f"[green]Buffer is full ({len(existing_unposted)} topics). Nothing to do.[/]")
        notifier = SlackNotifier()
        if notifier.enabled:
            notifier.send_daily_summary(existing_unposted[:n])
        return

    console.print(f"  Generating {needed} more topics to fill buffer...")

    stories = run_pipeline(n=needed)
    if not stories:
        console.print("[yellow]No new topics available to fill buffer.[/]")
        return

    enriched = enrich_and_save(stories)
    total = existing_unposted + enriched

    console.print(f"\n[bold green]Buffer: {len(total)} unposted topics ready.[/]")

    notifier = SlackNotifier()
    if notifier.enabled:
        notifier.send_daily_summary(total[:n])
        console.print(f"[green]Slack summary sent to channel.[/]")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="sourcing_agent — Phase 3 Topic Discovery Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Common
    parser.add_argument("--n", type=int, default=10, help="Number of topics to generate (default: 10)")
    parser.add_argument("--type", choices=["reactive", "educational"], help="Filter by content type")
    parser.add_argument("--verbose", action="store_true", help="Show per-source counts")

    # Modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Preview topics without saving")
    mode_group.add_argument("--interactive", action="store_true", help="Interactive topic selection")
    mode_group.add_argument("--search", metavar="QUERY", help="Search for specific educational topic")
    mode_group.add_argument("--watch", action="store_true", help="Daemon mode: continuous polling")
    mode_group.add_argument("--daily-buffer", action="store_true", help="Ensure N unposted topics exist")

    # Watch-specific
    parser.add_argument("--interval", type=int, help="Watch mode poll interval in minutes (default: 30)")
    parser.add_argument("--threshold", type=int, help="Watch mode score alert threshold (default: 75)")

    args = parser.parse_args()
    settings = load_settings()

    if args.watch:
        mode_watch(args, settings)
    elif args.daily_buffer:
        mode_daily_buffer(args, settings)
    elif args.dry_run:
        mode_dry_run(args, settings)
    elif args.interactive:
        mode_interactive(args, settings)
    elif args.search:
        mode_search(args, settings)
    else:
        mode_batch(args, settings)


if __name__ == "__main__":
    main()
