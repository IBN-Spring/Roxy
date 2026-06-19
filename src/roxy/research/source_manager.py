"""SourceManager — manage research feeds and info sources in config."""

from __future__ import annotations

from dataclasses import dataclass, field

from roxy.config.loader import Config


@dataclass
class FeedSource:
    """A configured RSS/Atom feed source."""

    name: str = ""
    url: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {"name": self.name, "url": self.url, "enabled": self.enabled}

    @classmethod
    def from_dict(cls, d: dict) -> "FeedSource":
        return cls(
            name=d.get("name", ""),
            url=d.get("url", ""),
            enabled=d.get("enabled", True),
        )


class SourceManager:
    """CRUD for research feed sources stored in Roxy config.

    Feeds live at config key `research.feeds` as a list of {name, url, enabled} dicts.
    """

    def __init__(self, config: Config):
        self.config = config
        self.config.load()

    # ── CRUD ─────────────────────────────────────────────────────

    def list_feeds(self, enabled_only: bool = False) -> list[FeedSource]:
        """List all configured feeds."""
        raw: list = self.config.get("research.feeds", [])
        feeds = [FeedSource.from_dict(f) for f in raw]
        if enabled_only:
            feeds = [f for f in feeds if f.enabled]
        return feeds

    def add_feed(self, name: str, url: str) -> FeedSource:
        """Add a new feed. Returns the created FeedSource."""
        feeds = self.list_feeds()

        # Check for duplicate URL
        for f in feeds:
            if f.url.strip().lower() == url.strip().lower():
                raise ValueError(f"Feed with URL '{url}' already exists (name: {f.name})")

        feed = FeedSource(name=name, url=url)
        feeds.append(feed)
        self._save(feeds)
        return feed

    def remove_feed(self, name: str) -> bool:
        """Remove a feed by name. Returns True if it existed."""
        feeds = self.list_feeds()
        matches = [f for f in feeds if f.name == name]
        if not matches:
            return False
        feeds = [f for f in feeds if f.name != name]
        self._save(feeds)
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a feed. Returns True if it existed."""
        feeds = self.list_feeds()
        found = False
        for f in feeds:
            if f.name == name:
                f.enabled = enabled
                found = True
        if found:
            self._save(feeds)
        return found

    # ── helpers ──────────────────────────────────────────────────

    def _save(self, feeds: list[FeedSource]) -> None:
        self.config.set("research.feeds", [f.to_dict() for f in feeds])
        self.config.save()
