""""roxy research" — manual research operations."""

import asyncio

import click
from rich.console import Console

console = Console()


@click.group("research")
def research_cmd() -> None:
    """Manual research operations.

    \b
    Examples:
      roxy research collect --channel rss --url "https://example.com/feed.xml"
    """
    pass


@research_cmd.command("collect")
@click.option("--channel", "-c", default="rss", help="Channel to collect from (default: rss).")
@click.option("--url", "-u", default="", help="Feed URL or search URL for the channel.")
@click.option("--topic", "-t", default="", help="Topic filter.")
@click.option("--since", default=None, help="ISO 8601 date — only items after this.")
@click.option("--max-items", default=50, help="Max items to fetch.")
def research_collect(
    channel: str,
    url: str,
    topic: str,
    since: str | None,
    max_items: int,
) -> None:
    """Collect research items from a channel and store in the knowledge base.

    \b
    Example:
      roxy research collect --channel rss --url "https://feeds.feedburner.com/Example"
    """
    from roxy.config.loader import Config
    from roxy.research.collector import ContentCollector

    if not url:
        console.print("[red]Error: --url is required for RSS channel.[/red]")
        console.print("Example: roxy research collect --channel rss --url \"https://example.com/feed.xml\"")
        return

    cfg = Config()
    cfg.load()

    async def _run():
        collector = ContentCollector(cfg)
        result = await collector.collect(
            channel_name=channel,
            feed_url=url,
            topic=topic,
            since=since,
            max_items=max_items,
        )
        return result

    console.print(f"[dim]Collecting from [cyan]{channel}[/cyan]: {url}...[/dim]")
    try:
        result = asyncio.run(_run())
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
    if result["items_new"] > 0:
        console.print(f"Search: [cyan]roxy knowledge search \"<keyword>\"[/cyan]")
    console.print()
