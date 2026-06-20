""""roxy eval" — evaluation and self-evolution tools (controlled, review-gated)."""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("eval")
def eval_cmd() -> None:
    """Evaluation and self-evolution tools.

    \b
    Baseline evaluation only. No automatic optimization.
    All evolved changes must be tested and human-reviewed.
    """
    pass


# ── seeds ────────────────────────────────────────────────────────

@eval_cmd.group("seeds")
def eval_seeds() -> None:
    """Generate evaluation seeds from traces."""
    pass


@eval_seeds.command("generate")
@click.option("--from", "source", default="traces", help="Source: traces (default).")
@click.option("--out", "-o", default="eval_seeds.jsonl", help="Output file path.")
@click.option("--max", "-n", "max_seeds", default=50, help="Max seeds to generate.")
def seeds_generate(source: str, out: str, max_seeds: int) -> None:
    """Generate evaluation seeds from agent traces."""
    from roxy.evolution.tracer import TraceRecorder

    count = TraceRecorder.generate_eval_seeds(Path(out), max_seeds=max_seeds)
    if count == 0:
        console.print("[yellow]No seeds generated. Chat with Roxy first to create traces.[/yellow]")
        return
    console.print(f"[green]✓[/green] Generated [cyan]{count}[/cyan] eval seeds → {out}")


# ── run ──────────────────────────────────────────────────────────

@eval_cmd.command("run")
@click.argument("cases_file", default="eval_seeds.jsonl")
@click.option("--out", "-o", default="eval_report.json", help="Output report path.")
@click.option("--live", is_flag=True, help="Run with live LLM (default: mock).")
@click.option("--model", "-m", default=None, help="Model to use (live mode only).")
def eval_run(cases_file: str, out: str, live: bool, model: str | None) -> None:
    """Run eval cases against the current agent.

    \b
    Default: uses mock provider (no API cost). Use --live for real evaluation.
    """
    from roxy.evolution.eval_runner import EvalRunner

    path = Path(cases_file)
    if not path.exists():
        console.print(f"[yellow]Cases file not found: {cases_file}[/yellow]")
        console.print("Generate seeds first: roxy eval seeds generate")
        return

    runner = EvalRunner(live=live)
    cases = runner.load_cases(path)
    if not cases:
        console.print("[yellow]No valid cases found in file.[/yellow]")
        return

    if not live:
        console.print(f"[dim]Running [cyan]{len(cases)}[/cyan] cases with mock provider...[/dim]")
        console.print("[dim]Use --live for real LLM evaluation.[/dim]")
    else:
        console.print(f"[dim]Running [cyan]{len(cases)}[/cyan] cases with live LLM...[/dim]")

    resolved_model = model or "mock"
    asyncio.run(runner.run(cases, model=resolved_model))

    report = runner.build_report(model=resolved_model)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    console.print()
    console.print(f"[green]✓[/green] Report saved → [cyan]{out}[/cyan]")
    console.print(f"  Total: {report['total']} | Passed: [green]{report['passed']}[/green] | Failed: [red]{report['failed']}[/red]")
    console.print(f"  Avg score: {report['avg_score']} | Avg latency: {report['avg_latency']}s")
    console.print()
    console.print(f"View details: [cyan]roxy eval report {out}[/cyan]")
    console.print(f"Generate proposals: [cyan]roxy eval propose {out}[/cyan]")


# ── report ───────────────────────────────────────────────────────

@eval_cmd.command("report")
@click.argument("report_file", default="eval_report.json")
def eval_report(report_file: str) -> None:
    """Display an eval report."""
    path = Path(report_file)
    if not path.exists():
        console.print(f"[yellow]Report not found: {report_file}[/yellow]")
        return

    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)

    console.print()
    console.print(f"[bold]Eval Report[/bold] — model: [cyan]{report.get('model', '—')}[/cyan] (live: {report.get('live', False)})")
    console.print()

    # Summary
    console.print(f"  Total cases:  {report['total']}")
    console.print(f"  Passed:       [green]{report['passed']}[/green]")
    console.print(f"  Failed:       [red]{report['failed']}[/red]")
    console.print(f"  Avg score:    {report['avg_score']}")
    console.print(f"  Min/Max:      {report['min_score']} / {report['max_score']}")
    console.print(f"  Avg latency:  {report['avg_latency']}s")
    console.print()

    # Failures
    failures = report.get("failures", [])
    if failures:
        console.print(f"[bold red]{len(failures)} failures:[/bold red]")
        for f in failures:
            reasons = "; ".join(f.get("reasons", []))
            console.print(f"  [red]✗[/red] {f['case_id']}: {reasons} (score: {f['score']})")
        console.print()

    # Per-case table
    results = report.get("results", [])
    if results:
        table = Table(title="Per-Case Results")
        table.add_column("Case", style="cyan")
        table.add_column("Passed")
        table.add_column("Tools", justify="right")
        table.add_column("Keywords", justify="right")
        table.add_column("Score", justify="right")

        for r in results:
            icon = "[green]✓[/green]" if r["passed"] else "[red]✗[/red]"
            table.add_row(
                r["case_id"][:20],
                icon,
                str(r["tool_use_match"]),
                str(r["keyword_recall"]),
                str(r["final_score"]),
            )
        console.print(table)
        console.print()


# ── propose ──────────────────────────────────────────────────────

@eval_cmd.command("propose")
@click.argument("report_file", default="eval_report.json")
@click.option("--out", "-o", default="", help="Output markdown path.")
@click.option("--target", "-t", default="all", help="Target: all, system-prompt, tool-descriptions.")
def eval_propose(report_file: str, out: str, target: str) -> None:
    """Generate improvement proposals from an eval report.

    \b
    Analyzes failed eval cases and produces actionable suggestions.
    Does NOT modify any files. Human review required.

    Example:
      roxy eval propose baseline.json --out proposals.md
    """
    from pathlib import Path
    from roxy.evolution.proposer import ProposalGenerator

    report_path = Path(report_file)
    if not report_path.exists():
        console.print(f"[yellow]Report not found: {report_file}[/yellow]")
        console.print("Run: roxy eval run eval_seeds.jsonl --out baseline.json")
        return

    # Default output path
    if not out:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        out = f"proposals-{date_str}.md"

    try:
        gen = ProposalGenerator()
        count = gen.generate(report_path, Path(out), target=target)
    except Exception as exc:
        console.print(f"[red]Proposal generation failed: {exc}[/red]")
        return

    if count == 0:
        console.print("[green]✓[/green] No failures — all cases passed. No proposals needed.")
    else:
        console.print(f"[green]✓[/green] Generated [cyan]{count}[/cyan] proposal(s) → [cyan]{out}[/cyan]")

    console.print()
    console.print("[dim]Review proposals before applying any changes.[/dim]")
    console.print("[dim]All changes must be test-gated and human-confirmed.[/dim]")


# ── compare ──────────────────────────────────────────────────────

@eval_cmd.command("compare")
@click.argument("baseline_file", default="baseline.json")
@click.argument("candidate_file", default="candidate.json")
def eval_compare(baseline_file: str, candidate_file: str) -> None:
    """Compare two eval reports side-by-side.

    \b
    Shows improvements, regressions, and unchanged cases.
    After making prompt/tool changes, use this to check for regressions.
    """
    import json
    from pathlib import Path
    from roxy.evolution.eval_runner import compare_reports

    for label, path in [("Baseline", baseline_file), ("Candidate", candidate_file)]:
        if not Path(path).exists():
            console.print(f"[yellow]{label} report not found: {path}[/yellow]")
            return

    with open(baseline_file, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    with open(candidate_file, "r", encoding="utf-8") as f:
        candidate = json.load(f)

    diff = compare_reports(baseline, candidate)

    console.print()
    console.print("[bold]Eval Compare[/bold]")
    console.print()

    # Metadata
    bm = diff.get("baseline_meta", {})
    cm = diff.get("candidate_meta", {})
    if bm or cm:
        console.print(f"  Baseline:  [dim]{bm.get('roxy_version', '—')}  {bm.get('git_commit', '')}  {bm.get('model', '')}[/dim]")
        console.print(f"  Candidate: [dim]{cm.get('roxy_version', '—')}  {cm.get('git_commit', '')}  {cm.get('model', '')}[/dim]")
        console.print()

    # Summary
    delta = diff["delta"]
    delta_str = f"[green]+{delta}[/green]" if delta > 0 else f"[red]{delta}[/red]" if delta < 0 else "0"
    console.print(f"  Baseline:  avg [cyan]{diff['baseline_avg']}[/cyan] | passed {diff['baseline_passed']}")
    console.print(f"  Candidate: avg [cyan]{diff['candidate_avg']}[/cyan] | passed {diff['candidate_passed']}")
    console.print(f"  Delta:     {delta_str}")
    console.print()

    # Improvements
    improvements = diff.get("improvements", [])
    if improvements:
        console.print(f"[bold green]{len(improvements)} improvement(s):[/bold green]")
        for imp in improvements:
            console.print(f"  [green]↑[/green] {imp['case_id']}: {imp['baseline_score']} → {imp['candidate_score']}"
                          f" (tool: {imp['baseline_tool']}→{imp['candidate_tool']}, kw: {imp['baseline_kw']}→{imp['candidate_kw']})")
        console.print()

    # Regressions
    regressions = diff.get("regressions", [])
    if regressions:
        console.print(f"[bold red]{len(regressions)} regression(s):[/bold red]")
        for reg in regressions:
            console.print(f"  [red]↓[/red] {reg['case_id']}: {reg['baseline_score']} → {reg['candidate_score']}"
                          f" (tool: {reg['baseline_tool']}→{reg['candidate_tool']}, kw: {reg['baseline_kw']}→{reg['candidate_kw']})")
        console.print()

    unchanged = diff.get("unchanged", [])
    if unchanged:
        console.print(f"[dim]{len(unchanged)} unchanged[/dim]")
        console.print()

    # Verdict
    if regressions:
        console.print("[red]⚠ Regressions found — review changes before applying.[/red]")
    elif not improvements:
        console.print("[dim]No significant changes detected.[/dim]")
    else:
        console.print("[green]✓ All improvements, no regressions. Safe to apply.[/green]")
    console.print()
