""""roxy eval" — evaluation seed generation (controlled evolution)."""

import click
from rich.console import Console

console = Console()


@click.group("eval")
def eval_cmd() -> None:
    """Evaluation and self-evolution tools.

    \b
    Currently: seed generation only. No automatic optimization.
    All evolved changes must be tested and human-reviewed.
    """
    pass


@eval_cmd.group("seeds")
def eval_seeds() -> None:
    """Generate evaluation seeds from traces.

    \b
    Seeds are input/output pairs that can be used to test
    prompt/skill/tool changes before applying them.
    """
    pass


@eval_seeds.command("generate")
@click.option("--from", "source", default="traces", help="Source: traces (default).")
@click.option("--out", "-o", default="eval_seeds.jsonl", help="Output file path.")
@click.option("--max", "-n", "max_seeds", default=50, help="Max seeds to generate.")
def seeds_generate(source: str, out: str, max_seeds: int) -> None:
    """Generate evaluation seeds from agent traces.

    \b
    Each seed contains:
      - task_input: the user's original message
      - expected_behavior: what a good response looks like
      - difficulty: easy (trace-derived defaults to easy)
      - category: trace-derived

    Seeds DO NOT auto-apply. Review before using for optimization.
    """
    from pathlib import Path
    from roxy.evolution.tracer import TraceRecorder

    count = TraceRecorder.generate_eval_seeds(Path(out), max_seeds=max_seeds)

    if count == 0:
        console.print("[yellow]No seeds generated. Chat with Roxy first to create traces.[/yellow]")
        return

    console.print(f"[green]✓[/green] Generated [cyan]{count}[/cyan] eval seeds → {out}")
    console.print()
    console.print("[dim]Review these seeds before using them for optimization.[/dim]")
    console.print("[dim]All evolved changes must be test-gated and human-confirmed.[/dim]")
