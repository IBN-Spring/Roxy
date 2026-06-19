""""roxy knowledge" — query and manage the knowledge base."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group("knowledge")
def knowledge_cmd() -> None:
    """Query and manage the Roxy knowledge base.

    \b
    Examples:
      roxy knowledge search "protein folding"
      roxy knowledge stats
    """
    pass


@knowledge_cmd.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Max results to show.")
@click.option("--tag", default=None, help="Filter by tag.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def knowledge_search(query: str, limit: int, tag: str | None, as_json: bool) -> None:
    """Full-text search the knowledge base."""
    from roxy.knowledge.store import KnowledgeStore
    from roxy.knowledge.query import KnowledgeQuery

    store = KnowledgeStore()
    store.init_db()

    q = KnowledgeQuery(store)
    results = q.search(query, limit=limit, tag=tag)

    if as_json:
        _output_json(results)
        return

    if not results:
        console.print(f"[yellow]No results found for '{query}'.[/yellow]")
        return

    console.print(f"\n[bold]Results for '[cyan]{query}[/cyan]':[/bold]")
    for entry in results:
        tags_str = ", ".join(entry.tags) if entry.tags else "—"
        source = entry.collected_via or "—"
        date = entry.published_at[:10] if entry.published_at else "—"

        panel_content = entry.content_plain or entry.summary or ""
        if len(panel_content) > 300:
            panel_content = panel_content[:300] + "..."

        console.print(
            Panel(
                panel_content or "(no content)",
                title=f"[bold]{entry.title}[/bold]",
                subtitle=f"{date} · {source} · tags: {tags_str}",
                title_align="left",
                border_style="cyan",
            )
        )
        if entry.canonical_url:
            console.print(f"  [dim]{entry.canonical_url}[/dim]")
        console.print()
    console.print(f"[dim]{len(results)} result(s)[/dim]")


@knowledge_cmd.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def knowledge_stats(as_json: bool) -> None:
    """Show knowledge base statistics."""
    from roxy.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    store.init_db()
    stats = store.get_stats()

    if as_json:
        import json
        click.echo(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
        return

    console.print()
    console.print("[bold]Knowledge Base Stats[/bold]")
    console.print(f"  Entries:  {stats['entry_count']}")
    console.print(f"  Tags:     {stats['tag_count']}")
    if stats["latest_entry"]:
        le = stats["latest_entry"]
        console.print(f"  Latest:   [cyan]{le.get('title', '—')}[/cyan] ({le.get('collected_at', '—')[:10]})")
    if stats["by_source"]:
        console.print("  By source:")
        for src, count in stats["by_source"].items():
            console.print(f"    {src}: {count}")
    console.print()


def _output_json(results) -> None:
    import json
    data = [r.to_okf_dict() for r in results]
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))
