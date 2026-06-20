"""Welcome panel for the Roxy chat TUI."""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from roxy import __version__


MASCOT = r"""
      /\_/\
   __/ o o \__
  /  \  ^  /  \
  |  /|___|\  |
  |_/  roxy \_|
      /_/\_\
"""


class WelcomePanel(Widget):
    """A compact Claude-Code-like getting-started panel."""

    DEFAULT_CSS = """
    WelcomePanel {
        width: 100%;
        height: auto;
        padding: 1 2 0 2;
    }
    """

    def __init__(
        self,
        model: str,
        session_id: str,
        workspace: Path,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.model = model
        self.session_id = session_id
        self.workspace = workspace

    def render(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=4)

        title = Text("Roxy", style="bold cyan")
        title.append("  vertical research agent", style="dim")

        info = Table.grid(padding=(0, 1))
        info.add_column(style="cyan", no_wrap=True)
        info.add_column()
        info.add_row("version", f"v{__version__}")
        info.add_row("model", self.model)
        info.add_row("session", self.session_id)
        info.add_row("workspace", str(self.workspace))

        tips = Text()
        tips.append("\nTips for getting started\n", style="bold")
        tips.append("• Ask a research question, or ask Roxy to search your knowledge base.\n")
        tips.append("• Add feeds with ")
        tips.append("roxy research feeds add \"Name\" \"URL\"", style="cyan")
        tips.append(".\n")
        tips.append("• Collect updates with ")
        tips.append("roxy research collect --all", style="cyan")
        tips.append(" and summarize with ")
        tips.append("roxy research digest", style="cyan")
        tips.append(".\n")
        tips.append("• Available tools: file_read, web_fetch, knowledge_query.", style="dim")

        right = Table.grid()
        right.add_row(title)
        right.add_row(info)
        right.add_row(tips)

        grid.add_row(Text(MASCOT, style="cyan"), right)

        return Panel(
            grid,
            title="Roxy Agent",
            subtitle="enter a message below",
            border_style="cyan",
            padding=(1, 2),
        )
