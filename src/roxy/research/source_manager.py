"""SourceManager — manage research feeds and info sources in config."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from roxy.config.loader import Config


@dataclass
class FeedSource:
    """A configured RSS/Atom feed source with collection state."""

    name: str = ""
    url: str = ""
    enabled: bool = True
    id: str = ""            # stable UUID for tracking across renames
    tags: list[str] = field(default_factory=list)
    last_run_at: str = ""   # ISO 8601 — last collection attempt
    last_success_at: str = ""  # ISO 8601 — last successful collection
    last_error: str = ""    # error message from last failed run
    total_collected: int = 0  # cumulative new entries collected

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "tags": self.tags,
            "last_run_at": self.last_run_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "total_collected": self.total_collected,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeedSource":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            url=d.get("url", ""),
            enabled=d.get("enabled", True),
            tags=d.get("tags", []),
            last_run_at=d.get("last_run_at", ""),
            last_success_at=d.get("last_success_at", ""),
            last_error=d.get("last_error", ""),
            total_collected=d.get("total_collected", 0),
        )

    @property
    def has_error(self) -> bool:
        return bool(self.last_error)


class SourceManager:
    """CRUD + state tracking for research feed sources stored in Roxy config.

    Feeds live at config key `research.feeds`.
    """

    def __init__(self, config: Config):
        self.config = config
        self.config.load()

    # ── CRUD ─────────────────────────────────────────────────────

    def list_feeds(self, enabled_only: bool = False) -> list[FeedSource]:
        raw: list = self.config.get("research.feeds", [])
        feeds = [FeedSource.from_dict(f) for f in raw]
        if enabled_only:
            feeds = [f for f in feeds if f.enabled]
        return feeds

    def get_feed(self, name: str) -> FeedSource | None:
        for f in self.list_feeds():
            if f.name == name:
                return f
        return None

    def add_feed(self, name: str, url: str, tags: list[str] | None = None) -> FeedSource:
        feeds = self.list_feeds()
        for f in feeds:
            if f.url.strip().lower() == url.strip().lower():
                raise ValueError(f"Feed with URL '{url}' already exists (name: {f.name})")

        feed = FeedSource(name=name, url=url, tags=tags or [])
        feeds.append(feed)
        self._save(feeds)
        return feed

    def remove_feed(self, name: str) -> bool:
        feeds = self.list_feeds()
        if not any(f.name == name for f in feeds):
            return False
        feeds = [f for f in feeds if f.name != name]
        self._save(feeds)
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        feeds = self.list_feeds()
        found = False
        for f in feeds:
            if f.name == name:
                f.enabled = enabled
                found = True
        if found:
            self._save(feeds)
        return found

    # ── state tracking ──────────────────────────────────────────

    def record_run(self, name: str) -> bool:
        """Mark a feed as having just been run. Returns True if feed found."""
        feeds = self.list_feeds()
        now = datetime.now(timezone.utc).isoformat()
        found = False
        for f in feeds:
            if f.name == name:
                f.last_run_at = now
                found = True
        if found:
            self._save(feeds)
        return found

    def record_success(self, name: str, new_count: int) -> bool:
        """Record a successful collection run."""
        feeds = self.list_feeds()
        now = datetime.now(timezone.utc).isoformat()
        found = False
        for f in feeds:
            if f.name == name:
                f.last_run_at = now
                f.last_success_at = now
                f.last_error = ""
                f.total_collected += new_count
                found = True
        if found:
            self._save(feeds)
        return found

    def record_error(self, name: str, error_msg: str) -> bool:
        """Record a failed collection run."""
        feeds = self.list_feeds()
        now = datetime.now(timezone.utc).isoformat()
        found = False
        for f in feeds:
            if f.name == name:
                f.last_run_at = now
                f.last_error = error_msg[:200]
                found = True
        if found:
            self._save(feeds)
        return found

    def get_status_summary(self) -> dict[str, Any]:
        """Return a summary of all feed statuses."""
        feeds = self.list_feeds()
        enabled = [f for f in feeds if f.enabled]
        with_errors = [f for f in feeds if f.has_error]
        never_run = [f for f in feeds if not f.last_run_at]

        return {
            "total": len(feeds),
            "enabled": len(enabled),
            "disabled": len(feeds) - len(enabled),
            "with_errors": len(with_errors),
            "never_run": len(never_run),
            "feeds": [f.to_dict() for f in feeds],
        }

    # ── helpers ──────────────────────────────────────────────────

    def _save(self, feeds: list[FeedSource]) -> None:
        self.config.set("research.feeds", [f.to_dict() for f in feeds])
        self.config.save()
