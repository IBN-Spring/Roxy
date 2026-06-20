""""roxy traces" — view and export agent execution traces."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("traces")
def trace_cmd() -> None:
    """View and export agent execution traces.

    \b
    Traces are recorded per-session in ~/.roxy/traces/.
    Privacy-safe: API keys masked, large results hashed.
    """
    pass


@trace_cmd.command("list")
@click.option("--limit", "-n", default=10, help="Max trace files to show.")
def traces_list(limit: int) -> None:
    """List trace files with turn counts."""
    from roxy.evolution.tracer import TraceRecorder

    traces = TraceRecorder.list_all_traces(limit=limit)
    if not traces:
        console.print("[dim]No traces recorded yet. Chat with Roxy to generate some.[/dim]")
        return

    table = Table(title="Trace Files")
    table.add_column("Session", style="cyan")
    table.add_column("Turns", justify="right")
    table.add_column("First", style="dim")
    table.add_column("Last", style="dim")

    for t in traces:
        first = t["first_at"][:16] if t["first_at"] else "—"
        last = t["last_at"][:16] if t["last_at"] else "—"
        table.add_row(t["session_id"][:12], str(t["turns"]), first, last)

    console.print(table)
    console.print(f"\n[dim]{len(traces)} trace file(s)[/dim]")


@trace_cmd.command("show")
@click.argument("session_id")
@click.option("--last", "-n", default=5, help="Show last N turns.")
def traces_show(session_id: str, last: int) -> None:
    """Show trace entries for a session."""
    from roxy.evolution.tracer import TraceRecorder

    recorder = TraceRecorder(session_id)
    turns = recorder.list_turns()
    if not turns:
        console.print(f"[yellow]No traces for session '{session_id}'.[/yellow]")
        return

    for turn in turns[-last:]:
        console.print(f"[bold cyan]{turn.get('user_message', '')[:80]}[/bold cyan]")
        tools = turn.get("tool_calls_summary", "")
        if tools:
            console.print(f"  🔧 {tools}")
        errs = turn.get("errors", "")
        if errs:
            console.print(f"  [red]Error: {errs[:100]}[/red]")
        console.print(f"  Model: {turn.get('model', '—')} | Duration: {turn.get('duration', 0)}s")
        final = turn.get("final_response", "")
        if final:
            console.print(f"  Response: {final[:120]}...")
        console.print()


@trace_cmd.command("export")
@click.option("--out", "-o", default="traces.jsonl", help="Output file path.")
def traces_export(out: str) -> None:
    """Export all traces to a single JSONL file."""
    from roxy.evolution.tracer import TraceRecorder

    count = TraceRecorder.export_all(Path(out))
    console.print(f"[green]✓[/green] Exported [cyan]{count}[/cyan] turns to {out}")
