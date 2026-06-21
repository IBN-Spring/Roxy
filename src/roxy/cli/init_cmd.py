""""roxy init" — onboarding setup wizard."""

import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from roxy.config.loader import Config
from roxy.config.paths import knowledge_db, knowledge_dir, roxy_home, sessions_dir

console = Console()


@click.command("init")
@click.option("--force", is_flag=True, help="Re-initialize even if already configured.")
@click.option("--yes", "-y", is_flag=True, help="Run non-interactively with defaults.")
@click.option("--quick", is_flag=True, help="Minimal: provider + key + workspace only.")
@click.option("--provider", default="", help="Provider key (deepseek, openai, ...).")
@click.option("--api-key", default="", help="Provider API key.")
@click.option("--model", default="", help="Override default model.")
@click.option("--name", default="", help="User display name.")
@click.option("--workspace", default="", help="Workspace directory.")
def init_cmd(
    force: bool, yes: bool, quick: bool,
    provider: str, api_key: str, model: str,
    name: str, workspace: str,
) -> None:
    """Set up Roxy for first use.

    \b
    Interactive wizard: choose provider, paste key, confirm workspace.
    """
    from roxy.models.presets import PROVIDER_PRESETS, get_preset, get_default_preset

    cfg = Config()
    cfg.load()

    already_configured = cfg.is_configured("user")
    if already_configured and not force:
        user_name = cfg.get("user.name")
        console.print(f"[yellow]Already configured for '{user_name}'.[/yellow]")
        if not Confirm.ask("Re-run setup?", default=False):
            return

    _print_welcome()

    # ── 1. Provider selection ──────────────────────────────
    preset = None

    if provider:
        preset = get_preset(provider)
        if not preset:
            # Treat as custom key
            preset = ProviderPreset(key=provider, label=provider.title(),
                                    default_model=f"{provider}/default")
    elif yes:
        preset = get_default_preset()
    else:
        _print_provider_menu()
        choice = Prompt.ask("  Choose provider", default="1")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(PROVIDER_PRESETS):
                preset = PROVIDER_PRESETS[idx]
        except ValueError:
            preset = get_preset(choice) or PROVIDER_PRESETS[0]

    if preset:
        console.print(f"\n[bold]Provider:[/bold] [cyan]{preset.label}[/cyan]")
        console.print(f"  Model:    [dim]{preset.default_model}[/dim]")
        if preset.base_url:
            console.print(f"  Base URL: [dim]{preset.base_url}[/dim]")
        console.print()

        # ── 2. API Key ──────────────────────────────────────
        if not api_key:
            env_val = os.environ.get(preset.env_var, "") if preset.env_var else ""
            if env_val:
                console.print(f"[green]✓[/green] Detected [cyan]{preset.env_var}[/cyan] from environment")
                api_key = env_val
            elif not yes:
                api_key = Prompt.ask(
                    f"  Paste your [cyan]{preset.label}[/cyan] API key",
                    password=True,
                )
                if not api_key and preset.env_var:
                    console.print(f"  [dim]No key entered. Set later via: export {preset.env_var}=\"<key>\"[/dim]")
                    console.print(f"  [dim]Or: roxy config set models.providers.{preset.key}.api_key \"<key>\"[/dim]")

        if api_key:
            cfg.set(f"models.providers.{preset.key}.api_key", api_key)
        if preset.base_url:
            cfg.set(f"models.providers.{preset.key}.base_url", preset.base_url)

        resolved_model = model or preset.default_model
        cfg.set("models.default", resolved_model)
        console.print(f"  Model set to: [cyan]{resolved_model}[/cyan]")

    # ── 3. Workspace ───────────────────────────────────────
    ws = workspace or cfg.get("workspace.path", "")
    if yes and not ws:
        ws = str(Path.cwd())
    elif not yes:
        ws = Prompt.ask("  Workspace directory", default=ws or str(Path.cwd()))
    if ws:
        cfg.set("workspace.path", str(Path(ws).expanduser().resolve()))
    console.print(f"  Workspace: [dim]{cfg.get('workspace.path')}[/dim]")

    # ── 4. Profile (skip in quick mode) ────────────────────
    if not quick and not yes:
        console.print()
        console.print("[bold]Profile[/bold] [dim](press Enter to skip)[/dim]")
        display_name = Prompt.ask("  What should I call you?", default=cfg.get("user.name", name or ""))
        if display_name:
            cfg.set("user.name", display_name)
        identity = Prompt.ask("  Your role?", default=cfg.get("user.identity", ""))
        if identity:
            cfg.set("user.identity", identity)
    elif name:
        cfg.set("user.name", name)

    # ── 5. Bootstrap runtime ───────────────────────────────
    _bootstrap_runtime()
    cfg.save()

    # ── 6. Success page ────────────────────────────────────
    console.print()
    console.print(Panel(
        _success_text(cfg, preset),
        title="[bold green]Roxy is ready![/bold green]",
        border_style="green",
    ))
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  [cyan]roxy doctor[/cyan]        Check everything is working")
    console.print(f"  [cyan]roxy chat[/cyan]          Start the TUI")
    console.print(f"  [cyan]/status[/cyan]              Check runtime state")
    console.print(f"  [cyan]/evolve[/cyan]              View source evolution pipeline")
    console.print()


# ── display helpers ─────────────────────────────────────────

def _print_welcome():
    console.print()
    console.print("[bold cyan]Roxy Setup[/bold cyan] — source-level self-evolving agent")
    console.print("[dim]Choose your model provider, paste your API key, and you're ready.[/dim]")
    console.print()


def _print_provider_menu():
    console.print("[bold]Choose your model provider:[/bold]")
    console.print()
    for i, p in enumerate(PROVIDER_PRESETS, 1):
        rec = " [green]★ recommended[/green]" if p.recommended else ""
        console.print(f"  [cyan]{i}.[/cyan] [bold]{p.label}[/bold]{rec}")
        console.print(f"     [dim]{p.description}[/dim]")
    console.print(f"  [cyan]0.[/cyan] Custom (enter provider key manually)")
    console.print()


def _bootstrap_runtime():
    roxy_home()
    sessions_dir()
    knowledge_dir()
    try:
        from roxy.knowledge.store import KnowledgeStore
        ks = KnowledgeStore()
        ks.init_db()
    except Exception:
        pass


def _success_text(cfg, preset) -> str:
    lines = ["", ""]
    if preset:
        lines.append(f"  Provider:   [cyan]{preset.label}[/cyan]")
        lines.append(f"  Model:      [cyan]{cfg.get('models.default')}[/cyan]")
    key_status = "[green]configured[/green]" if preset and cfg.get(f"models.providers.{preset.key}.api_key") else "[yellow]not set[/yellow]"
    lines.append(f"  API Key:    {key_status}")
    lines.append(f"  Workspace:  [dim]{cfg.get('workspace.path', '')}[/dim]")
    lines.append(f"  Runtime:    [dim]{roxy_home()}[/dim]")
    lines.append("")
    return "\n".join(lines)


# Fix missing import for Custom provider path
from roxy.models.presets import ProviderPreset
