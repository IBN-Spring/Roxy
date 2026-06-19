""""roxy init" — first-time setup and bootstrap."""

from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from roxy.config.loader import Config
from roxy.config.paths import knowledge_db, knowledge_dir, roxy_home, sessions_dir


console = Console()


@click.command("init")
@click.option("--force", is_flag=True, help="Re-initialize even if already configured.")
@click.option("--yes", "-y", is_flag=True, help="Run non-interactively with sensible defaults.")
@click.option("--name", default="", help="User display name.")
@click.option("--identity", default="", help="User role or profession.")
@click.option("--domain", default="", help="Primary research domain.")
@click.option("--topic", "topics", multiple=True, help="Research topic. May be used multiple times.")
@click.option("--feed", "feeds", multiple=True, help="RSS feed as NAME=URL. May be used multiple times.")
@click.option("--workspace", default="", help="Workspace directory. Defaults to current directory in --yes mode.")
@click.option("--provider", default="openai", help="LLM provider name.")
@click.option("--model", default="", help="Default model, e.g. openai/gpt-4.1-mini.")
@click.option("--api-key", default="", help="Provider API key. Prefer env vars for real secrets.")
@click.option("--base-url", default="", help="Optional provider base URL.")
@click.option("--wechat-db", default="", help="Path to wechat-query rss.db.")
@click.option("--skip-provider", is_flag=True, help="Do not prompt for model provider configuration.")
def init_cmd(
    force: bool,
    yes: bool,
    name: str,
    identity: str,
    domain: str,
    topics: tuple[str, ...],
    feeds: tuple[str, ...],
    workspace: str,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    wechat_db: str,
    skip_provider: bool,
) -> None:
    """Set up Roxy for first use.

    Interactive mode asks for your profile, model, sources, and workspace.
    `--yes` bootstraps a usable local setup without prompts.
    """
    cfg = Config()
    cfg.load()

    already_configured = cfg.is_configured("user")
    if already_configured and not force:
        name = cfg.get("user.name")
        console.print(f"[yellow]Already configured for '{name}'.[/yellow]")
        if not Confirm.ask("Re-run setup?", default=False):
            return

    _print_header(yes)

    # ── User profile ────────────────────────────────────────────

    name = name or _ask("  What should I call you?", cfg.get("user.name", ""), yes)
    if name:
        cfg.set("user.name", name)

    identity = identity or _ask("  What's your role / profession?", cfg.get("user.identity", ""), yes)
    if identity:
        cfg.set("user.identity", identity)

    domain = domain or _ask("  What's your primary research domain?", cfg.get("user.research_domain", ""), yes)
    if domain:
        cfg.set("user.research_domain", domain)

    # ── Topics ──────────────────────────────────────────────────

    existing_topics: list = cfg.get("user.topics", [])
    if topics:
        cfg.set("user.topics", list(topics))
    elif not yes:
        topics_str = Prompt.ask(
            "  Research topics (comma-separated)",
            default=", ".join(existing_topics) if existing_topics else "",
        )
        if topics_str.strip():
            cfg.set("user.topics", [t.strip() for t in topics_str.split(",") if t.strip()])

    # ── Info sources ────────────────────────────────────────────

    existing_sources: list = cfg.get("user.info_sources", [])
    if feeds:
        _set_feeds(cfg, feeds)
        cfg.set("user.info_sources", [f.split("=", 1)[1].strip() for f in feeds if "=" in f])
    elif not yes:
        console.print("  [dim]Info sources — RSS feeds, websites, etc. (comma-separated)[/dim]")
        sources_str = Prompt.ask(
            "  Information sources",
            default=", ".join(existing_sources) if existing_sources else "",
        )
        if sources_str.strip():
            cfg.set("user.info_sources", [s.strip() for s in sources_str.split(",") if s.strip()])

    # ── Workspace ────────────────────────────────────────────────

    workspace = workspace or cfg.get("workspace.path", "")
    if yes and not workspace:
        workspace = str(Path.cwd())
    elif not yes:
        workspace = Prompt.ask("  Workspace directory", default=workspace or str(Path.cwd()))
    if workspace:
        cfg.set("workspace.path", str(Path(workspace).expanduser().resolve()))

    # ── LLM provider ────────────────────────────────────────────

    if not skip_provider:
        console.print()
        console.print("[bold]LLM Provider Setup[/bold]")
        console.print("[dim]You can add more providers later via `roxy config set models.providers.<name>.api_key <key>`[/dim]")

    add_provider = False if skip_provider else (True if yes else Confirm.ask("  Configure a model provider now?", default=True))
    if add_provider:
        provider_name = provider if yes else Prompt.ask("  Provider name", default=provider)
        provider_key_map: dict[str, Any] = cfg.get(f"models.providers.{provider_name}", {}) or {}
        api_key = api_key or ("" if yes else Prompt.ask(f"  API key for '{provider_name}'", default=provider_key_map.get("api_key", ""), password=True))
        if api_key:
            cfg.set(f"models.providers.{provider_name}.api_key", api_key)

        base_url = base_url or ("" if yes else Prompt.ask(
            "  Base URL (optional, press Enter for default)",
            default=provider_key_map.get("base_url", ""),
        ))
        if base_url:
            cfg.set(f"models.providers.{provider_name}.base_url", base_url)

        model = model or (cfg.get("models.default", f"{provider_name}/gpt-4.1-mini") if yes else Prompt.ask(
            "  Default model",
            default=cfg.get("models.default", f"{provider_name}/gpt-4.1-mini"),
        ))
        cfg.set("models.default", model)

    # ── WeChat adapter path ──────────────────────────────────────

    if wechat_db:
        cfg.set("research.wechat.db_path", str(Path(wechat_db).expanduser()))
    elif not yes:
        current_wechat = cfg.get("research.wechat.db_path", "")
        if Confirm.ask("  Configure wechat-query DB path?", default=bool(current_wechat)):
            db_path = Prompt.ask("  wechat-query rss.db path", default=current_wechat or "~/wechat-query/data/rss.db")
            cfg.set("research.wechat.db_path", db_path)

    # ── Save ─────────────────────────────────────────────────────

    console.print()
    _bootstrap_runtime()
    cfg.save()
    console.print(f"[green]✓ Configuration saved to {cfg._path}[/green]")
    console.print(f"[green]✓ Runtime home ready at {roxy_home()}[/green]")
    console.print(f"[green]✓ Knowledge DB ready at {knowledge_db()}[/green]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  [cyan]roxy doctor[/cyan]   Check everything is working")
    console.print(f"  [cyan]roxy chat[/cyan]     Start chatting")
    console.print(f"  [cyan]roxy research feeds add \"Name\" \"URL\"[/cyan]  Add a source")
    console.print()


def _print_header(non_interactive: bool) -> None:
    console.print()
    console.print("[bold cyan]╔══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║       Welcome to Roxy Setup!        ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/bold cyan]")
    console.print()
    if non_interactive:
        console.print("Bootstrapping Roxy with non-interactive defaults.")
    else:
        console.print("I'll ask a few questions and prepare your local Roxy runtime.")
        console.print("[dim](Press Enter to skip any question)[/dim]")
    console.print()


def _ask(label: str, default: str, non_interactive: bool) -> str:
    if non_interactive:
        return default
    return Prompt.ask(label, default=default)


def _set_feeds(cfg: Config, feed_specs: tuple[str, ...]) -> None:
    feeds = []
    for spec in feed_specs:
        if "=" not in spec:
            raise click.ClickException("--feed must be in NAME=URL format")
        name, url = spec.split("=", 1)
        name = name.strip()
        url = url.strip()
        if name and url:
            feeds.append({"name": name, "url": url, "enabled": True})
    if feeds:
        cfg.set("research.feeds", feeds)


def _bootstrap_runtime() -> None:
    roxy_home()
    sessions_dir()
    knowledge_dir()
    from roxy.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    store.init_db()
    store.close()
