""""roxy dev" — development and release checks."""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group("dev")
def dev_cmd() -> None:
    """Development tools and release checks."""
    pass


@dev_cmd.command("check")
@click.option("--quick", is_flag=True, help="Skip full test suite.")
def dev_check(quick: bool) -> None:
    """Run release readiness checks.

    \b
    Checks: version, pytest, doctor, imports, CLI smoke.
    Use before committing or tagging a release.
    """
    from roxy import __version__

    passed = 0
    failed = 0

    def check(name: str, fn) -> None:
        nonlocal passed, failed
        try:
            fn()
            console.print(f"  [green]✓[/green] {name}")
            passed += 1
        except Exception as exc:
            console.print(f"  [red]✗[/red] {name} — {exc}")
            failed += 1

    console.print(f"\n[bold]Roxy v{__version__} — Dev Check[/bold]\n")

    # Version
    check("version matches", lambda: _assert(__version__ == "0.6.0", f"Expected 0.6.0, got {__version__}"))

    # Imports
    check("core imports", lambda: _import_all(["roxy", "roxy.config", "roxy.engine", "roxy.tools", "roxy.knowledge", "roxy.research", "roxy.evolution"]))
    check("CLI imports", lambda: _import_all(["roxy.cli.main", "roxy.cli.init_cmd", "roxy.cli.doctor_cmd", "roxy.cli.chat_cmd", "roxy.cli.knowledge_cmd", "roxy.cli.research_cmd", "roxy.cli.monitor_cmd", "roxy.cli.trace_cmd", "roxy.cli.eval_cmd"]))
    check("TUI imports", lambda: _import("roxy.tui.app"))

    # CLI smoke
    check("roxy --version", lambda: _run([sys.executable, "-m", "roxy", "--version"]))
    check("roxy doctor --json", lambda: _run([sys.executable, "-m", "roxy", "doctor", "--json"]))
    check("roxy knowledge stats", lambda: _run([sys.executable, "-m", "roxy", "knowledge", "stats"]))

    # Tests
    if quick:
        console.print(f"  [dim]○ pytest (skipped, use without --quick)[/dim]")
    else:
        def run_tests():
            _run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=Path(__file__).parent.parent.parent.parent)
        check("pytest tests/", run_tests)

    # Eval smoke (mock)
    def eval_smoke():
        import json, tempfile, asyncio
        from roxy.evolution.eval_runner import EvalRunner
        cases = [{"task_input": "hello"}]
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        with open(tmp, "w") as f:
            for c in cases:
                f.write(json.dumps(c) + "\n")
        try:
            runner = EvalRunner(live=False)
            loaded = runner.load_cases(tmp)
            asyncio.run(runner.run(loaded))
            report = runner.build_report()
            _assert(report["total"] == 1, f"Expected 1 case, got {report['total']}")
        finally:
            tmp.unlink()
    check("eval mock run", eval_smoke)

    console.print()
    total = passed + failed
    if failed == 0:
        console.print(f"[bold green]{passed}/{total} checks passed — ready to release![/bold green]")
    else:
        console.print(f"[bold red]{failed}/{total} checks failed — fix before releasing.[/bold red]")
        raise SystemExit(1)
    console.print()


def _assert(condition, msg):
    if not condition:
        raise AssertionError(msg)


def _import(name):
    import importlib
    importlib.import_module(name)


def _import_all(names):
    for n in names:
        _import(n)


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:200] if r.stderr else f"exit {r.returncode}")
