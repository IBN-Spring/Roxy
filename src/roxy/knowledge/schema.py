"""Knowledge base schema — SQLite DDL + OKF canonical JSON shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── OKF Canonical JSON Shape (v0.1) ─────────────────────────────
# This is the portable interchange format. Every entry exported as one JSON line.
# SQLite is the runtime store; JSONL is the portable export/import format.

OKF_JSON_SCHEMA: dict[str, Any] = {
    "okf_version": "0.1",
    "id": "uuid",
    "type": "source | item | insight | topic",
    "canonical_url": "https://...",
    "title": "Human-readable title",
    "content_md": "Full content as Markdown",
    "content_plain": "Plain text excerpt (first 500 chars)",
    "summary": "AI-generated 1-3 sentence summary",
    "authors": ["author names"],
    "published_at": "ISO 8601",
    "collected_at": "ISO 8601",
    "collected_via": "rss | web | search | wechat | manual | agent",
    "language": "zh-CN",
    "tags": ["tag1", "tag2"],
    "topics": ["topic_id"],
    "source": {
        "type": "rss_feed | web_page | search_result | wechat_mp | import",
        "feed_url": "...",
        "channel_name": "...",
    },
    "relations": {
        "parent_id": None,
        "related_ids": [],
        "follow_up_of": None,
    },
    "insights": [
        {
            "text": "Key takeaway or viewpoint",
            "confidence": 0.8,
            "generated_by": "model_name",
            "generated_at": "ISO 8601",
        }
    ],
    "follow_ups": [
        {
            "question": "Unresolved question worth investigating",
            "status": "open | investigating | answered",
            "priority": "low | medium | high",
        }
    ],
}

# ── SQLite DDL ──────────────────────────────────────────────────

SQLITE_SCHEMA = """
-- Core entries table
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    okf_type TEXT NOT NULL DEFAULT 'item',
    title TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    content_md TEXT DEFAULT '',
    content_plain TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    authors TEXT DEFAULT '[]',          -- JSON array
    published_at TEXT DEFAULT '',        -- ISO 8601
    collected_at TEXT NOT NULL,          -- ISO 8601
    collected_via TEXT DEFAULT 'manual',
    language TEXT DEFAULT 'zh-CN',
    source_type TEXT DEFAULT '',
    source_feed_url TEXT DEFAULT '',
    source_channel TEXT DEFAULT '',
    content_hash TEXT NOT NULL,          -- SHA256 for dedup
    UNIQUE(content_hash)
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    content_plain,
    summary,
    content='entries',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, content_plain, summary)
    VALUES (new.rowid, new.title, new.content_plain, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content_plain, summary)
    VALUES ('delete', old.rowid, old.title, old.content_plain, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content_plain, summary)
    VALUES ('delete', old.rowid, old.title, old.content_plain, old.summary);
    INSERT INTO entries_fts(rowid, title, content_plain, summary)
    VALUES (new.rowid, new.title, new.content_plain, new.summary);
END;

-- Tags (flat, no hierarchy for now)
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

-- Follow-up questions
CREATE TABLE IF NOT EXISTS follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'low',
    created_at TEXT NOT NULL
);

-- Collection log (for debugging / auditing)
CREATE TABLE IF NOT EXISTS collection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT DEFAULT '',
    channel_name TEXT NOT NULL,
    source_name TEXT DEFAULT '',
    feed_url TEXT DEFAULT '',
    items_found INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    items_duplicate INTEGER DEFAULT 0,
    errors TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_collection_log_run ON collection_log(run_id);
CREATE INDEX IF NOT EXISTS idx_collection_log_started ON collection_log(started_at);
"""


# ── Dataclass for in-memory representation ─────────────────────

@dataclass
class KnowledgeEntry:
    """In-memory representation of a knowledge base entry."""

    id: str = ""
    okf_type: str = "item"
    title: str = ""
    canonical_url: str = ""
    content_md: str = ""
    content_plain: str = ""
    summary: str = ""
    authors: list[str] = field(default_factory=list)
    published_at: str = ""
    collected_at: str = ""
    collected_via: str = "manual"
    language: str = "zh-CN"
    source_type: str = ""
    source_feed_url: str = ""
    source_channel: str = ""
    content_hash: str = ""
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def to_okf_dict(self) -> dict[str, Any]:
        """Export to OKF canonical JSON dict."""
        import json

        return {
            "okf_version": "0.1",
            "id": self.id,
            "type": self.okf_type,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "content_md": self.content_md,
            "content_plain": self.content_plain[:500],
            "summary": self.summary,
            "authors": self.authors,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "collected_via": self.collected_via,
            "language": self.language,
            "tags": self.tags,
            "topics": self.topics,
            "source": {
                "type": self.source_type,
                "feed_url": self.source_feed_url,
                "channel_name": self.source_channel,
            },
            "relations": {"parent_id": None, "related_ids": [], "follow_up_of": None},
            "insights": [],
            "follow_ups": [],
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "KnowledgeEntry":
        """Create from a SQLite row dict."""
        import json

        authors = []
        if row.get("authors"):
            try:
                authors = json.loads(row["authors"])
            except (json.JSONDecodeError, TypeError):
                authors = []

        return cls(
            id=row.get("id", ""),
            okf_type=row.get("okf_type", "item"),
            title=row.get("title", ""),
            canonical_url=row.get("canonical_url", ""),
            content_md=row.get("content_md", ""),
            content_plain=row.get("content_plain", ""),
            summary=row.get("summary", ""),
            authors=authors,
            published_at=row.get("published_at", ""),
            collected_at=row.get("collected_at", ""),
            collected_via=row.get("collected_via", "manual"),
            language=row.get("language", "zh-CN"),
            source_type=row.get("source_type", ""),
            source_feed_url=row.get("source_feed_url", ""),
            source_channel=row.get("source_channel", ""),
            content_hash=row.get("content_hash", ""),
        )
