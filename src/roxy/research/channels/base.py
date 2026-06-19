"""Channel ABC + ResearchItem — the interface all research channels implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from roxy.config.loader import Config


@dataclass
class ResearchItem:
    """A single research finding from a channel.

    This is the standard envelope that all channels produce.
    ContentCollector passes these to KnowledgeWriter.
    """

    title: str
    canonical_url: str
    content_md: str = ""
    content_plain: str = ""
    summary: str = ""
    authors: list[str] = field(default_factory=list)
    published_at: str = ""  # ISO 8601
    collected_at: str = ""  # ISO 8601
    collected_via: str = "rss"
    language: str = ""
    source_type: str = ""
    source_feed_url: str = ""
    source_channel: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "canonical_url": self.canonical_url,
            "content_md": self.content_md,
            "content_plain": self.content_plain,
            "summary": self.summary,
            "authors": self.authors,
            "published_at": self.published_at,
            "collected_at": self.collected_at or datetime.now().isoformat(),
            "collected_via": self.collected_via,
            "language": self.language,
            "source_type": self.source_type,
            "source_feed_url": self.source_feed_url,
            "source_channel": self.source_channel,
            "tags": self.tags,
        }


class Channel(ABC):
    """Abstract base class for all research channels.

    Modeled on Agent-Reach's Channel pattern, extended with async collect().
    Each channel represents a source of research content: RSS feeds, web search,
    GitHub releases, arXiv papers, etc.
    """

    name: str = ""
    description: str = ""
    tier: int = 0  # 0=zero-config, 1=needs key, 2=complex setup

    @abstractmethod
    async def check(self, config: Config) -> tuple[str, str]:
        """Verify the channel is usable. Returns (status, message).

        status: "ok" | "warn" | "off" | "error"
        """
        ...

    @abstractmethod
    async def collect(
        self,
        config: Config,
        topic: str = "",
        since: str | None = None,
    ) -> list[ResearchItem]:
        """Collect research items from this channel.

        Args:
            config: Roxy config (for API keys, feed URLs, etc.).
            topic: Optional topic filter (channel-dependent interpretation).
            since: ISO 8601 date string — only return items published after this.

        Returns:
            List of ResearchItem objects.
        """
        ...

    def can_handle(self, source: str) -> bool:
        """Return True if this channel can handle the given source string.

        Default: checks if the source starts with the channel name.
        Override for URL-based detection.
        """
        return source.lower().startswith(self.name.lower())
