""""roxy doctor" — health check command."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

from roxy.config.loader import Config
from roxy.models.health import ProviderHealth

console = Console()


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed probe results.")
def doctor_cmd(as_json: bool, verbose: bool) -> None:
    """Check the health of your Roxy installation.

    Verifies configuration, provider connectivity, and workspace state.
    """
    cfg = Config()
    cfg.load()

    if as_json:
        _doctor_json(cfg, verbose)
    else:
        _doctor_rich(cfg, verbose)


def _doctor_rich(cfg: Config, verbose: bool) -> None:
    """Print a Rich-formatted health report."""
    console.print()
    console.print("[bold]Roxy Doctor Report[/bold]", highlight=False)
    console.print()

    # ── Config ──────────────────────────────────────────────────
    config_path = cfg._path
    if config_path.exists():
        console.print(f"[green]✓[/green] Config found at {config_path}")
    else:
        console.print(f"[yellow]![/yellow] No config found. Run [cyan]roxy init[/cyan] first.")
        return

    # ── User profile ─────────────────────────────────────────────
    console.print()
    console.print("[bold]User Profile:[/bold]")
    name = cfg.get("user.name")
    identity = cfg.get("user.identity")
    domain = cfg.get("user.research_domain")
    topics = cfg.get("user.topics", [])

    if name:
        console.print(f"  Name:             {name}")
    else:
        console.print("  [yellow]Name: not set[/yellow]")
    if identity:
        console.print(f"  Identity:         {identity}")
    if domain:
        console.print(f"  Research domain:  {domain}")
    if topics:
        console.print(f"  Topics:           {', '.join(topics)}")

    # ── Workspace ────────────────────────────────────────────────
    workspace = cfg.get("workspace.path", "")
    console.print()
    console.print("[bold]Workspace:[/bold]")
    if workspace:
        import os
        wspath = os.path.expanduser(workspace)
        if os.path.isdir(wspath):
            console.print(f"[green]✓[/green] {wspath}")
        else:
            console.print(f"[yellow]![/yellow] {wspath} (directory does not exist)")
    else:
        console.print("[dim]  No workspace set (defaults to current directory)[/dim]")

    # ── Providers ────────────────────────────────────────────────
    console.print()
    health = ProviderHealth(cfg)
    results = health.check_all()
    console.print(health.format_report(results))

    # ── Tools ────────────────────────────────────────────────────
    console.print()
    console.print("[bold]Available Tools:[/bold]")
    try:
        from roxy.tools.registry import ToolRegistry
        from roxy.tools.builtin import ReadFileTool, WebFetchTool, KnowledgeQueryTool

        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WebFetchTool())
        registry.register(KnowledgeQueryTool())

        for t in registry.get_all():
            risk_style = {"safe": "green", "caution": "yellow", "dangerous": "red"}.get(t.risk_level.value, "dim")
            ws = "📁" if t.workspace_bounded else "🌐"
            console.print(f"  [{risk_style}]{t.name}[/{risk_style}] {ws} {t.description}")
    except Exception:
        console.print("  [dim]Tools not available (install roxy with all dependencies)[/dim]")

    # ── Runtime ──────────────────────────────────────────────────
    console.print()
    console.print("[bold]Runtime:[/bold]")
    from roxy.config.paths import roxy_home, knowledge_db, sessions_dir
    console.print(f"  Home:      {roxy_home()}")
    console.print(f"  Config:    {cfg._path}{' [green]✓[/green]' if cfg._path.exists() else ' [yellow]![/yellow]'}")

    # KB status
    try:
        from roxy.knowledge.store import KnowledgeStore
        ks = KnowledgeStore()
        ks.init_db()
        stats = ks.get_stats()
        console.print(f"  Knowledge: {stats['entry_count']} entries, {stats['tag_count']} tags "
                      f"({knowledge_db()})")
    except Exception:
        console.print(f"  Knowledge: [dim]unavailable[/dim]")

    # Sessions count
    try:
        session_files = list(sessions_dir().glob("*.json"))
        console.print(f"  Sessions:  {len(session_files)} saved ({sessions_dir()})")
    except Exception:
        console.print(f"  Sessions:  [dim]unavailable[/dim]")

    # ── Research Channels ─────────────────────────────────────────
    console.print()
    console.print("[bold]Research Channels:[/bold]")
    try:
        from roxy.research.channels import ALL_CHANNELS, RSSChannel

        cfg_copy = Config()
        cfg_copy.load()
        for ch in ALL_CHANNELS:
            tier_icon = {0: "🟢", 1: "🟡", 2: "🔴"}.get(ch.tier, "⚪")
            try:
                status, msg = asyncio.run(ch.check(cfg_copy))
            except Exception:
                status, msg = "error", "check failed"
            status_icon = {"ok": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "off": "[dim]○[/dim]"}.get(status, "[red]✗[/red]")
            console.print(f"  {tier_icon} {status_icon} [cyan]{ch.name}[/cyan] — {ch.description}")
            if status != "ok":
                console.print(f"       [dim]{msg}[/dim]")
    except Exception:
        console.print("  [dim]Channels not available[/dim]")

    # ── Summary ──────────────────────────────────────────────────
    console.print()
    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    warn_count = sum(1 for r in results.values() if r["status"] == "warn")
    total = len(results) if results else 1
    default_model = cfg.get("models.default", "not set")
    console.print(f"Default model: [cyan]{default_model}[/cyan]")
    console.print(f"Providers: {ok_count} ok, {warn_count} warn, {total - ok_count - warn_count} error")
    console.print()

    if ok_count == 0 and warn_count == 0:
        console.print("[yellow]No providers configured. Run [cyan]roxy init[/cyan] to set up.[/yellow]")
    elif ok_count > 0:
        console.print("[green]Ready to chat! Run [cyan]roxy chat[/cyan].[/green]")
    else:
        console.print("[yellow]Providers configured but API keys may be missing.[/yellow]")
        console.print()
        _print_key_fix_hints(results, default_model)
        console.print()

    # Env var detection
    _print_env_key_hints()


def _print_key_fix_hints(results: dict, default_model: str) -> None:
    """Print per-provider key configuration commands."""
    console.print("[bold]Fix with one of these:[/bold]")
    for name in sorted(results.keys()):
        provider = name
        env_var = _KNOWN_ENV(provider)
        console.print(f"  [cyan]roxy config set models.providers.{provider}.api_key \"<your-key>\"[/cyan]")
        if env_var:
            console.print(f"  or: [cyan]export {env_var}=\"<your-key>\"[/cyan]")


def _print_env_key_hints() -> None:
    """Detect if any well-known env vars are already set."""
    import os
    found: list[str] = []
    for provider, env_var in _ENV_MAP.items():
        if os.environ.get(env_var):
            found.append(f"{env_var} (for {provider})")
    if found:
        console.print("[dim]Detected env vars: " + ", ".join(found) + "[/dim]")
        console.print("[dim]Use /model <provider>/<model> to switch, or set models.default in config.[/dim]")


_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
}


def _KNOWN_ENV(provider: str) -> str:
    return _ENV_MAP.get(provider.lower(), "")


def _doctor_json(cfg: Config, verbose: bool) -> None:
    """Print JSON health report."""
    import json

    health = ProviderHealth(cfg)
    results = health.check_all()

    # Tool summary
    tools_info: list[dict] = []
    try:
        from roxy.tools.registry import ToolRegistry
        from roxy.tools.builtin import ReadFileTool, WebFetchTool, KnowledgeQueryTool
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WebFetchTool())
        registry.register(KnowledgeQueryTool())
        tools_info = registry.tool_summary()
    except Exception:
        pass

    # Runtime info
    from roxy.config.paths import roxy_home, knowledge_db, sessions_dir

    kb_stats = {}
    try:
        from roxy.knowledge.store import KnowledgeStore
        ks = KnowledgeStore()
        ks.init_db()
        kb_stats = ks.get_stats()
    except Exception:
        pass

    sessions_count = 0
    try:
        sessions_count = len(list(sessions_dir().glob("*.json")))
    except Exception:
        pass

    # Channel summary
    channels_info: list[dict] = []
    try:
        from roxy.research.channels import ALL_CHANNELS
        for ch in ALL_CHANNELS:
            channels_info.append({
                "name": ch.name,
                "description": ch.description,
                "tier": ch.tier,
            })
    except Exception:
        pass

    report = {
        "config_path": str(cfg._path),
        "config_exists": cfg._path.exists(),
        "runtime": {
            "home": str(roxy_home()),
            "knowledge_db": str(knowledge_db()),
            "sessions_dir": str(sessions_dir()),
            "sessions_count": sessions_count,
        },
        "knowledge": kb_stats,
        "user": {
            "name": cfg.get("user.name"),
            "identity": cfg.get("user.identity"),
            "research_domain": cfg.get("user.research_domain"),
            "topics": cfg.get("user.topics"),
        },
        "default_model": cfg.get("models.default"),
        "providers": {k: v for k, v in results.items()},
        "tools": tools_info,
        "channels": channels_info,
    }
    click.echo(json.dumps(report, indent=2, ensure_ascii=False, default=str))
