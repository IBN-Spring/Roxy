"""Channel ABC + ResearchItem — the interface all research channels implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from roxy.config.loader import Config


@dataclass
class ResearchItem:
    """A single research finding from a channel."""

    title: str
    canonical_url: str
    content_md: str = ""
    content_plain: str = ""
    summary: str = ""
    authors: list[str] = field(default_factory=list)
    published_at: str = ""
    collected_at: str = ""
    collected_via: str = "rss"
    language: str = ""
    source_type: str = ""
    source_feed_url: str = ""
    source_channel: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title, "canonical_url": self.canonical_url,
            "content_md": self.content_md, "content_plain": self.content_plain,
            "summary": self.summary, "authors": self.authors,
            "published_at": self.published_at,
            "collected_at": self.collected_at or datetime.now().isoformat(),
            "collected_via": self.collected_via, "language": self.language,
            "source_type": self.source_type, "source_feed_url": self.source_feed_url,
            "source_channel": self.source_channel, "tags": self.tags,
        }


class Channel(ABC):
    """Abstract base class for all research channels.

    v0.4.0: standardized capability contract with config requirements,
    repair hints, and external adapter protocol.
    """

    name: str = ""
    description: str = ""
    tier: int = 0                     # 0=zero-config, 1=needs key/path, 2=complex
    requires_config: list[str] = []   # Config keys needed, e.g. ["research.wechat.db_path"]
    config_keys: dict[str, str] = {}  # Human-readable: {"research.wechat.db_path": "Path to wechat-query rss.db"}

    # ── capability contract ──────────────────────────────────────

    @abstractmethod
    async def check(self, config: Config) -> tuple[str, str]:
        """Verify the channel is usable. Returns (status, message).

        status: "ok" | "warn" | "off" | "error"
        """
        ...

    @abstractmethod
    async def collect(
        self, config: Config, topic: str = "", since: str | None = None
    ) -> list[ResearchItem]:
        """Collect research items from this channel."""
        ...

    def can_handle(self, source: str) -> bool:
        """Return True if this channel can handle the given source string."""
        return source.lower().startswith(self.name.lower())

    # ── v0.4.0: repair hints ────────────────────────────────────

    def repair_hint(self, status: str, message: str) -> str:
        """Return an actionable repair command based on check() status.

        Override for channel-specific fixes. The default covers common cases.
        """
        if status == "ok":
            return ""

        if status == "off":
            # Missing config — suggest setting required keys
            hints = []
            for key in self.requires_config:
                desc = self.config_keys.get(key, key)
                hints.append(f"  roxy config set {key} \"<value>\"  # {desc}")
            if hints:
                return "\n".join([f"Channel '{self.name}' needs configuration:"] + hints)
            return f"Channel '{self.name}' is not available. Check: roxy doctor"

        if status == "warn":
            return f"Channel '{self.name}' has warnings: {message}"

        if status == "error":
            return f"Channel '{self.name}' error: {message}\n  Check: roxy doctor"

        return ""

    def capability_summary(self) -> dict[str, Any]:
        """Return a dict describing this channel for doctor / status display."""
        return {
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "requires_config": self.requires_config,
            "config_keys": self.config_keys,
        }
