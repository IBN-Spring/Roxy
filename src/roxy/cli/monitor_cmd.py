""""roxy monitor" — unified background research collection."""

import asyncio
import uuid

import click
from rich.console import Console

console = Console()


@click.group("monitor")
def monitor_cmd() -> None:
    """Run research monitoring operations.

    \b
    Default: collects from all enabled feeds + all enabled topics.
    """
    pass


@monitor_cmd.command("run")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
@click.option("--max-items", default=50, help="Max items per feed/topic.")
@click.option("--feeds-only", is_flag=True, help="Only collect from feeds.")
@click.option("--topics-only", is_flag=True, help="Only collect from topics.")
def monitor_run(as_json: bool, max_items: int, feeds_only: bool, topics_only: bool) -> None:
    """Collect from all enabled feeds and topics.

    \b
    Cron example (every 6 hours):
      0 */6 * * * roxy monitor run --json >> ~/.roxy/monitor.log
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager
    from roxy.research.topic_manager import TopicManager
    from roxy.research.collector import ContentCollector
    from datetime import datetime, timezone

    cfg = Config(); cfg.load()
    collector = ContentCollector(cfg)

    run_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    feed_results = []
    topic_results = []
    total_new = 0
    total_dup = 0
    errors = []

    # ── Feeds ──────────────────────────────────────────────────
    do_feeds = not topics_only
    if do_feeds:
        sm = SourceManager(cfg)
        feeds = sm.list_feeds(enabled_only=True)
        if feeds:
            if not as_json:
                console.print(f"[dim]Feeds: [cyan]{len(feeds)}[/cyan][/dim]")
            for feed in feeds:
                try:
                    result = asyncio.run(collector.collect(
                        channel_name="rss", feed_url=feed.url, feed_name=feed.name,
                        run_id=run_id, max_items=max_items,
                    ))
                    feed_results.append({
                        "feed": feed.name, "url": feed.url,
                        "items_found": result["items_found"],
                        "items_new": result["items_new"],
                        "items_duplicate": result["items_duplicate"],
                    })
                    total_new += result["items_new"]
                    total_dup += result["items_duplicate"]
                    if result.get("errors"):
                        errors.extend(result["errors"])
                    if not as_json:
                        icon = "✓" if not result.get("errors") else "✗"
                        console.print(f"  {icon} [cyan]{feed.name}[/cyan]: {result['items_new']} new")
                except Exception as exc:
                    feed_results.append({"feed": feed.name, "url": feed.url, "error": str(exc)})
                    errors.append(f"feed:{feed.name}: {exc}")
                    if not as_json:
                        console.print(f"  [red]✗ {feed.name}: {exc}[/red]")

    # ── Topics ─────────────────────────────────────────────────
    do_topics = not feeds_only
    if do_topics:
        tm = TopicManager(cfg)
        topics = tm.list_topics(enabled_only=True)
        if topics:
            if not as_json:
                console.print(f"[dim]Topics: [cyan]{len(topics)}[/cyan][/dim]")
            for topic in topics:
                for ch_name in topic.channels:
                    try:
                        result = asyncio.run(collector.collect(
                            channel_name=ch_name, topic=topic.query,
                            run_id=run_id, max_items=max_items,
                        ))
                        topic_results.append({
                            "topic": topic.name, "channel": ch_name,
                            "items_found": result["items_found"],
                            "items_new": result["items_new"],
                            "items_duplicate": result["items_duplicate"],
                        })
                        total_new += result["items_new"]
                        total_dup += result["items_duplicate"]
                        if result.get("errors"):
                            errors.extend(result["errors"])
                        if not as_json:
                            icon = "✓" if not result.get("errors") else "✗"
                            console.print(f"  {icon} [cyan]{topic.name}[/cyan]→{ch_name}: {result['items_new']} new")
                    except Exception as exc:
                        topic_results.append({"topic": topic.name, "channel": ch_name, "error": str(exc)})
                        errors.append(f"topic:{topic.name}/{ch_name}: {exc}")
                        if not as_json:
                            console.print(f"  [red]✗ {topic.name}→{ch_name}: {exc}[/red]")

    # ── Output ─────────────────────────────────────────────────
    if as_json:
        import json
        output = {
            "status": "ok" if not errors else "partial",
            "run_id": run_id,
            "started_at": started_at,
            "total_new": total_new,
            "total_dup": total_dup,
            "errors": errors,
            "feed_results": feed_results,
            "topic_results": topic_results,
        }
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
        if errors:
            raise SystemExit(1)
    else:
        console.print()
        console.print(f"[bold]Run [cyan]{run_id[:8]}[/cyan] complete.[/bold]")
        console.print(f"  Feeds: {len(feed_results)}  |  Topics: {len(topic_results)}")
        console.print(f"  New: [green]{total_new}[/green]  |  Duplicates: {total_dup}")
        if errors:
            console.print(f"  Errors: [red]{len(errors)}[/red]")
        console.print()

    if errors and not as_json:
        raise SystemExit(1)

    # No feeds or topics at all
    if not feed_results and not topic_results:
        msg = "No enabled feeds or topics configured."
        if as_json:
            import json
            click.echo(json.dumps({"status": "no_sources", "message": msg}))
        else:
            console.print(f"[yellow]{msg}[/yellow]")
