"""TopicManager — manage saved research topics for multi-channel queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from roxy.config.loader import Config


@dataclass
class ResearchTopic:
    """A saved research topic for monitoring across channels."""

    name: str = ""
    query: str = ""             # search query string
    channels: list[str] = field(default_factory=lambda: ["arxiv"])  # which channels to query
    enabled: bool = True
    id: str = ""
    tags: list[str] = field(default_factory=list)
    last_run_at: str = ""
    last_error: str = ""
    total_collected: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.query:
            self.query = self.name

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "query": self.query,
            "channels": self.channels, "enabled": self.enabled,
            "tags": self.tags, "last_run_at": self.last_run_at,
            "last_error": self.last_error, "total_collected": self.total_collected,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchTopic":
        return cls(
            id=d.get("id", ""), name=d.get("name", ""), query=d.get("query", ""),
            channels=d.get("channels", ["arxiv"]), enabled=d.get("enabled", True),
            tags=d.get("tags", []), last_run_at=d.get("last_run_at", ""),
            last_error=d.get("last_error", ""), total_collected=d.get("total_collected", 0),
        )


class TopicManager:
    """CRUD + state tracking for research topics stored in config.

    Topics live at config key `research.topics_data`.
    """

    def __init__(self, config: Config):
        self.config = config
        self.config.load()

    def list_topics(self, enabled_only: bool = False) -> list[ResearchTopic]:
        raw: list = self.config.get("research.topics_data", [])
        topics = [ResearchTopic.from_dict(t) for t in raw]
        if enabled_only:
            topics = [t for t in topics if t.enabled]
        return topics

    def get_topic(self, name: str) -> ResearchTopic | None:
        for t in self.list_topics():
            if t.name == name:
                return t
        return None

    def add_topic(self, name: str, query: str = "", channels: list[str] | None = None) -> ResearchTopic:
        topics = self.list_topics()
        for t in topics:
            if t.name == name:
                raise ValueError(f"Topic '{name}' already exists")

        topic = ResearchTopic(name=name, query=query or name, channels=channels or ["arxiv"])
        topics.append(topic)
        self._save(topics)
        return topic

    def remove_topic(self, name: str) -> bool:
        topics = self.list_topics()
        if not any(t.name == name for t in topics):
            return False
        self._save([t for t in topics if t.name != name])
        return True

    def set_enabled(self, name: str, enabled: bool) -> bool:
        topics = self.list_topics()
        found = False
        for t in topics:
            if t.name == name:
                t.enabled = enabled
                found = True
        if found:
            self._save(topics)
        return found

    def record_success(self, name: str, new_count: int) -> bool:
        topics = self.list_topics()
        now = datetime.now(timezone.utc).isoformat()
        found = False
        for t in topics:
            if t.name == name:
                t.last_run_at = now
                t.last_error = ""
                t.total_collected += new_count
                found = True
        if found:
            self._save(topics)
        return found

    def record_error(self, name: str, error_msg: str) -> bool:
        topics = self.list_topics()
        now = datetime.now(timezone.utc).isoformat()
        found = False
        for t in topics:
            if t.name == name:
                t.last_run_at = now
                t.last_error = error_msg[:200]
                found = True
        if found:
            self._save(topics)
        return found

    def _save(self, topics: list[ResearchTopic]) -> None:
        self.config.set("research.topics_data", [t.to_dict() for t in topics])
        self.config.save()
