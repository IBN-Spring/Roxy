""""roxy research" — manual research operations."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("research")
def research_cmd() -> None:
    """Manual research operations.

    \b
    Examples:
      roxy research feeds list
      roxy research collect --url "https://example.com/feed.xml"
      roxy research collect --all
      roxy research digest
    """
    pass


# ── feeds ────────────────────────────────────────────────────────

@research_cmd.group("feeds")
def research_feeds() -> None:
    """Manage configured research feed sources.

    \b
    Examples:
      roxy research feeds add "My Feed" "https://example.com/rss"
      roxy research feeds list
      roxy research feeds remove "My Feed"
    """
    pass


@research_feeds.command("list")
def feeds_list() -> None:
    """List all configured RSS feed sources."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    feeds = sm.list_feeds()

    if not feeds:
        console.print("[yellow]No feeds configured.[/yellow]")
        console.print("Add one: [cyan]roxy research feeds add \"Name\" \"https://example.com/rss\"[/cyan]")
        return

    table = Table(title="Research Feeds")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="dim")
    table.add_column("Status")

    for f in feeds:
        status = "[green]enabled[/green]" if f.enabled else "[dim]disabled[/dim]"
        table.add_row(f.name, f.url, status)

    console.print(table)


@research_feeds.command("add")
@click.argument("name")
@click.argument("url")
def feeds_add(name: str, url: str) -> None:
    """Add a new RSS feed source.

    \b
    Example:
      roxy research feeds add "Hacker News" "https://hnrss.org/frontpage"
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    try:
        feed = sm.add_feed(name, url)
        console.print(f"[green]✓[/green] Added feed: [cyan]{feed.name}[/cyan] ({feed.url})")
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")


@research_feeds.command("remove")
@click.argument("name")
def feeds_remove(name: str) -> None:
    """Remove a feed by name."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    if sm.remove_feed(name):
        console.print(f"[green]✓[/green] Removed feed: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


@research_feeds.command("status")
@click.argument("name", required=False)
def feeds_status(name: str | None) -> None:
    """Show feed collection status.

    \b
    Without arguments: summary of all feeds.
    With a feed name: detailed status for that feed.
    """
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)

    if name:
        feed = sm.get_feed(name)
        if not feed:
            console.print(f"[yellow]Feed not found: '{name}'[/yellow]")
            return
        _print_feed_detail(feed)
    else:
        _print_feed_summary(sm)


@research_feeds.command("enable")
@click.argument("name")
def feeds_enable(name: str) -> None:
    """Enable a feed."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    if sm.set_enabled(name, True):
        console.print(f"[green]✓[/green] Enabled: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


@research_feeds.command("disable")
@click.argument("name")
def feeds_disable(name: str) -> None:
    """Disable a feed (stops it from being collected with --all)."""
    from roxy.config.loader import Config
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()
    sm = SourceManager(cfg)
    if sm.set_enabled(name, False):
        console.print(f"[green]✓[/green] Disabled: [cyan]{name}[/cyan]")
    else:
        console.print(f"[yellow]Feed not found: '{name}'[/yellow]")


# ── feed display helpers ────────────────────────────────────────


def _print_feed_detail(feed) -> None:
    from roxy.research.source_manager import FeedSource

    console.print()
    console.print(f"[bold cyan]{feed.name}[/bold cyan]")
    console.print(f"  URL:       {feed.url}")
    console.print(f"  Status:    {'[green]enabled[/green]' if feed.enabled else '[dim]disabled[/dim]'}")
    console.print(f"  Tags:      {', '.join(feed.tags) if feed.tags else '—'}")
    console.print(f"  Total collected: {feed.total_collected}")
    console.print(f"  Last run:  {feed.last_run_at[:19] if feed.last_run_at else 'never'}")
    console.print(f"  Last success: {feed.last_success_at[:19] if feed.last_success_at else 'never'}")
    if feed.last_error:
        console.print(f"  Last error: [red]{feed.last_error}[/red]")
    console.print()


def _print_feed_summary(sm) -> None:
    summary = sm.get_status_summary()
    console.print()
    console.print("[bold]Feed Status Summary[/bold]")
    console.print(f"  Total:   {summary['total']}")
    console.print(f"  Enabled: [green]{summary['enabled']}[/green]")
    console.print(f"  Disabled: {summary['disabled']}")
    if summary['with_errors']:
        console.print(f"  With errors: [red]{summary['with_errors']}[/red]")
    if summary['never_run']:
        console.print(f"  Never run: [yellow]{summary['never_run']}[/yellow]")
    console.print()

    if summary['feeds']:
        from rich.table import Table
        table = Table(title="Feeds")
        table.add_column("Name", style="cyan")
        table.add_column("Status")
        table.add_column("Collected", justify="right")
        table.add_column("Last Run")
        table.add_column("Last Error", style="red")

        for f in summary['feeds']:
            status = "[green]enabled[/green]" if f["enabled"] else "[dim]disabled[/dim]"
            last_run = f["last_run_at"][:16] if f["last_run_at"] else "never"
            err = f["last_error"][:40] if f["last_error"] else "—"
            table.add_row(f["name"], status, str(f["total_collected"]), last_run, err)

        console.print(table)
        console.print()


# ── collect ──────────────────────────────────────────────────────

@research_cmd.command("collect")
@click.option("--channel", "-c", default="rss", help="Channel to collect from (default: rss).")
@click.option("--url", "-u", default="", help="Feed URL or search URL for the channel.")
@click.option("--all", "collect_all", is_flag=True, help="Collect from ALL configured feeds.")
@click.option("--topic", "-t", default="", help="Topic filter.")
@click.option("--since", default=None, help="ISO 8601 date — only items after this.")
@click.option("--max-items", default=50, help="Max items per feed.")
def research_collect(
    channel: str,
    url: str,
    collect_all: bool,
    topic: str,
    since: str | None,
    max_items: int,
) -> None:
    """Collect research items and store in the knowledge base.

    \b
    Examples:
      roxy research collect --channel rss --url "https://example.com/feed.xml"
      roxy research collect --all
    """
    from roxy.config.loader import Config
    from roxy.research.collector import ContentCollector
    from roxy.research.source_manager import SourceManager

    cfg = Config()
    cfg.load()

    async def _collect_one(ch: str, u: str, fn: str = "") -> dict:
        collector = ContentCollector(cfg)
        return await collector.collect(
            channel_name=ch,
            feed_url=u,
            topic=topic,
            since=since,
            max_items=max_items,
            feed_name=fn,
        )

    if collect_all:
        sm = SourceManager(cfg)
        feeds = sm.list_feeds(enabled_only=True)
        if not feeds:
            console.print("[yellow]No enabled feeds configured.[/yellow]")
            console.print("Add one: [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]")
            return

        console.print(f"[dim]Collecting from [cyan]{len(feeds)}[/cyan] feed(s)...[/dim]")
        total_new = 0
        total_dup = 0
        total_found = 0

        for feed in feeds:
            console.print(f"  [cyan]{feed.name}[/cyan]...", end=" ")
            try:
                result = asyncio.run(_collect_one("rss", feed.url, fn=feed.name))
                total_found += result.get("items_found", 0)
                total_new += result.get("items_new", 0)
                total_dup += result.get("items_duplicate", 0)
                errs = result.get("errors", [])
                if errs:
                    console.print(f"[red]✗ {errs[0]}[/red]")
                else:
                    console.print(f"[green]{result['items_new']} new[/green], {result['items_duplicate']} dup")
            except Exception as exc:
                console.print(f"[red]✗ {exc}[/red]")

        console.print()
        console.print("[bold green]Collection complete:[/bold green]")
        console.print(f"  Feeds processed:  {len(feeds)}")
        console.print(f"  Items found:      {total_found}")
        console.print(f"  New entries:      [green]{total_new}[/green]")
        console.print(f"  Duplicates:       [yellow]{total_dup}[/yellow]")
        console.print()
        if total_new > 0:
            console.print(f"Search: [cyan]roxy knowledge search \"<keyword>\"[/cyan]")
            console.print(f"Digest: [cyan]roxy research digest[/cyan]")
        console.print()
        return

    # Single URL mode
    if not url and channel == "rss":
        console.print("[red]Error: --url is required (or use --all for configured feeds).[/red]")
        console.print("Example: roxy research collect --url \"https://example.com/feed.xml\"")
        return

    console.print(f"[dim]Collecting from [cyan]{channel}[/cyan]: {url}...[/dim]")
    try:
        result = asyncio.run(_collect_one(channel, url))
    except Exception as exc:
        console.print(f"[red]Collection failed: {exc}[/red]")
        return

    if result.get("errors"):
        for err in result["errors"]:
            console.print(f"[red]  Error: {err}[/red]")
        return

    console.print()
    console.print("[bold green]Collection complete:[/bold green]")
    console.print(f"  Items found:      {result['items_found']}")
    console.print(f"  New entries:      [green]{result['items_new']}[/green]")
    console.print(f"  Duplicates:       [yellow]{result['items_duplicate']}[/yellow]")
    console.print()


# ── digest ───────────────────────────────────────────────────────

@research_cmd.command("digest")
@click.option("--days", "-d", default=7, help="Look back this many days (default: 7).")
@click.option("--source", "-s", default=None, help="Filter by source (rss, web, manual).")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def research_digest(days: int, source: str | None, as_json: bool) -> None:
    """Generate a digest of recent knowledge base entries.

    \b
    Example:
      roxy research digest --days 3
    """
    from roxy.research.digest import ResearchDigest

    dg = ResearchDigest()
    result = dg.generate(days=days, collected_via=source)

    if as_json:
        import json
        click.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    console.print()
    console.print(f"[bold]Research Digest[/bold] — last {days} day(s)")
    console.print(f"[dim]Generated: {result['generated_at'][:19]}[/dim]")
    console.print()

    if result["entry_count"] == 0:
        console.print("[yellow]No entries found in this period.[/yellow]")
        console.print("Collect some: [cyan]roxy research collect --all[/cyan]")
        return

    console.print(result["summary_text"])
    console.print(f"[dim]{result['entry_count']} entries from {len(result['by_source'])} source(s)[/dim]")
