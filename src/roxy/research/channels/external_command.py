"""ExternalCommandChannel — base class for channels backed by external CLI tools.

Roxy keeps its core clean by calling external tools rather than importing their
source code. This base class provides the protocol for command-based channels:

  - check(): verify the external command exists on PATH
  - repair_hint(): suggest installation command
  - run_command(): execute the external tool with timeout and capture output

Subclasses for specific tools: Agent-Reach, arXiv CLI, GitHub CLI, etc.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any

from roxy.config.loader import Config
from roxy.research.channels.base import Channel, ResearchItem

logger = logging.getLogger(__name__)


class ExternalCommandChannel(Channel):
    """Base class for channels that wrap an external CLI tool.

    Subclasses override:
      - command_name: the binary name (e.g. "agent-reach")
      - install_hint_cmd: how to install it (e.g. "pip install agent-reach")
      - check(): verify availability
      - collect(): run the tool and parse output
    """

    command_name: str = ""
    install_hint_cmd: str = ""
    command_timeout: float = 30.0
    tier: int = 1  # external tools need setup

    def command_available(self) -> bool:
        """Return True if the external command is found on PATH."""
        if not self.command_name:
            return False
        return shutil.which(self.command_name) is not None

    async def run_command(self, args: list[str], timeout: float | None = None) -> tuple[int, str, str]:
        """Run the external command. Returns (returncode, stdout, stderr)."""
        timeout = timeout or self.command_timeout
        full_args = [self.command_name] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *full_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return -1, "", f"Command timed out after {timeout}s"
        except FileNotFoundError:
            return -1, "", f"Command '{self.command_name}' not found"
        except Exception as exc:
            return -1, "", str(exc)

    def repair_hint(self, status: str, message: str) -> str:
        if status == "off" and self.install_hint_cmd:
            return (
                f"External tool '[cyan]{self.command_name}[/cyan]' not found.\n"
                f"  Install: [cyan]{self.install_hint_cmd}[/cyan]\n"
                f"  Or set custom path in config."
            )
        return super().repair_hint(status, message)
