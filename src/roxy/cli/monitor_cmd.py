""""roxy monitor" — run background research collection."""

import asyncio

import click
from rich.console import Console

console = Console()


@click.group("monitor")
def monitor_cmd() -> None:
    """Run research monitoring operations.

    \b
    Examples:
      roxy monitor run            Collect from all configured feeds once
      roxy monitor run --json     Output results as JSON (cron-friendly)
    """
    pass


@monitor_cmd.command("run")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
@click.option("--max-items", default=50, help="Max items per feed.")
def monitor_run(as_json: bool, max_items: int) -> None:
    """Collect from all enabled feeds once.

    Designed to be cron-friendly: use --json for structured output.
    Exit code 0 on success, 1 on any error.

    \b
    Cron example (every 6 hours):
      0 */6 * * * roxy monitor run --json >> ~/.roxy/monitor.log
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager
    from roxy.research.collector import ContentCollector

    cfg = Config()
    cfg.load()

    sm = SourceManager(cfg)
    feeds = sm.list_feeds(enabled_only=True)

    if not feeds:
        msg = "No enabled feeds configured."
        if as_json:
            import json
            click.echo(json.dumps({"status": "no_feeds", "message": msg}))
        else:
            console.print(f"[yellow]{msg}[/yellow]")
        return

    if not as_json:
        console.print(f"[dim]Monitor: collecting from [cyan]{len(feeds)}[/cyan] feed(s)...[/dim]")

    collector = ContentCollector(cfg)
    run = asyncio.run(collector.collect_feeds(feeds, max_items=max_items))
    results = run["results"]
    total_new = run["total_new"]
    errors = run["errors"]

    if as_json:
        import json
        output = {
            "status": "ok" if not errors else "partial",
            "run_id": run["run_id"],
            "started_at": run["started_at"],
            "feeds_processed": run["feeds_processed"],
            "total_new": total_new,
            "total_dup": run["total_dup"],
            "errors": errors,
            "results": results,
        }
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))
        if errors:
            raise SystemExit(1)
    else:
        console.print()
        for r in results:
            icon = "✓" if "error" not in r else "✗"
            console.print(f"  {icon} [cyan]{r['feed']}[/cyan]: {r['items_new']} new, {r['items_duplicate']} dup")
        console.print()
        console.print(f"[bold]Total new: [green]{total_new}[/green][/bold]")

    if errors and not as_json:
        raise SystemExit(1)
