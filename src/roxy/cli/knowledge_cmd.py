""""roxy knowledge" — query and manage the knowledge base."""

import json
from pathlib import Path

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
      roxy knowledge export --out kb.jsonl
      roxy knowledge import kb.jsonl
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

        console.print(Panel(
            panel_content or "(no content)",
            title=f"[bold]{entry.title}[/bold]",
            subtitle=f"{date} · {source} · tags: {tags_str}",
            title_align="left", border_style="cyan",
        ))
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


# ── export ──────────────────────────────────────────────────────

@knowledge_cmd.command("export")
@click.option("--format", "-f", "fmt", default="okf", help="Export format (default: okf).")
@click.option("--out", "-o", default="kb.jsonl", help="Output file path.")
def knowledge_export(fmt: str, out: str) -> None:
    """Export the knowledge base as OKF JSONL.

    \b
    Example:
      roxy knowledge export --out kb.jsonl
    """
    from roxy.knowledge.store import KnowledgeStore

    path = Path(out)
    store = KnowledgeStore()
    store.init_db()
    count = store.export_jsonl(path)

    console.print(f"[green]✓[/green] Exported [cyan]{count}[/cyan] entries to {path}")
    console.print(f"Format: OKF v0.1 (JSONL)")


# ── import ──────────────────────────────────────────────────────

@knowledge_cmd.command("import")
@click.argument("path")
@click.option("--no-validate", is_flag=True, help="Skip OKF schema validation.")
def knowledge_import(path: str, no_validate: bool) -> None:
    """Import entries from an OKF JSONL file.

    \b
    Example:
      roxy knowledge import kb.jsonl
    """
    from roxy.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    store.init_db()
    counts = store.import_jsonl(Path(path), validate=not no_validate)

    console.print()
    console.print(f"[green]✓[/green] Imported: [cyan]{counts['imported']}[/cyan]")
    if counts["skipped"]:
        console.print(f"  Skipped (duplicates): [yellow]{counts['skipped']}[/yellow]")
    if counts["errors"]:
        console.print(f"  Errors: [red]{counts['errors']}[/red]")
    console.print()


# ── validate ────────────────────────────────────────────────────

@knowledge_cmd.command("validate")
@click.argument("path")
def knowledge_validate(path: str) -> None:
    """Validate a JSONL file against the OKF v0.1 schema.

    \b
    Example:
      roxy knowledge validate kb.jsonl
    """
    from roxy.knowledge.okf_validator import validate_file

    result = validate_file(Path(path))

    if result["total"] == 0:
        console.print("[yellow]No entries found in file.[/yellow]")
        return

    if result["valid"]:
        console.print(f"[green]✓[/green] All [cyan]{result['total']}[/cyan] entries are valid OKF v0.1.")
    else:
        console.print(f"[red]✗[/red] {len(result['errors'])} of {result['total']} entries have errors:")
        for err in result["errors"]:
            console.print(f"  Line {err['line']}:")
            for e in err["errors"]:
                console.print(f"    [red]{e}[/red]")
        raise SystemExit(1)


# ── schema ──────────────────────────────────────────────────────

@knowledge_cmd.command("schema")
def knowledge_schema() -> None:
    """Show the OKF v0.1 JSON Schema."""
    from roxy.knowledge.okf_schema import OKF_JSON_SCHEMA, OKF_VERSION

    console.print(f"\n[bold]OKF v{OKF_VERSION} JSON Schema[/bold]\n")
    console.print_json(json.dumps(OKF_JSON_SCHEMA, indent=2))


# ── helpers ──────────────────────────────────────────────────────

def _output_json(results) -> None:
    data = [r.to_okf_dict() for r in results]
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))
