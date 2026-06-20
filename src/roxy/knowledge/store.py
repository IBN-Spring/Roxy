"""KnowledgeStore — SQLite-backed knowledge base with FTS5 search."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy.config.paths import knowledge_db
from roxy.knowledge.schema import KnowledgeEntry, SQLITE_SCHEMA

logger = logging.getLogger(__name__)


class KnowledgeStore:
    """SQLite-backed knowledge store with full-text search.

    Usage:
        store = KnowledgeStore()
        store.init_db()
        store.insert_entry(entry)
        results = store.search("keyword")
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or knowledge_db()
        self._conn: sqlite3.Connection | None = None

    # ── connection ───────────────────────────────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── init ─────────────────────────────────────────────────────

    def init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        self.conn.executescript(SQLITE_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns that may be missing from older DB versions."""
        existing = {r[1] for r in self.conn.execute(
            "PRAGMA table_info(collection_log)"
        ).fetchall()}
        migrations = [
            ("run_id", "TEXT DEFAULT ''"),
            ("source_name", "TEXT DEFAULT ''"),
        ]
        for col_name, col_def in migrations:
            if col_name not in existing:
                try:
                    self.conn.execute(
                        f"ALTER TABLE collection_log ADD COLUMN {col_name} {col_def}"
                    )
                    self.conn.commit()
                except Exception:
                    pass

    # ── CRUD ─────────────────────────────────────────────────────

    def insert_entry(self, entry: KnowledgeEntry) -> tuple[bool, str]:
        """Insert an entry. Returns (is_new, entry_id).

        Deduplication: entries with the same content_hash are skipped.
        content_hash = SHA256(canonical_url + title) if not provided.
        """
        if not entry.id:
            entry.id = uuid.uuid4().hex[:16]

        if not entry.collected_at:
            entry.collected_at = datetime.now(timezone.utc).isoformat()

        if not entry.content_hash:
            entry.content_hash = _make_hash(entry.canonical_url, entry.title)

        # Check for duplicate
        existing = self.conn.execute(
            "SELECT id FROM entries WHERE content_hash = ?",
            (entry.content_hash,),
        ).fetchone()

        if existing:
            return False, existing["id"]

        # Insert
        try:
            self.conn.execute(
                """INSERT INTO entries (
                    id, okf_type, title, canonical_url,
                    content_md, content_plain, summary,
                    authors, published_at, collected_at, collected_via,
                    language, source_type, source_feed_url, source_channel,
                    content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.okf_type,
                    entry.title,
                    entry.canonical_url,
                    entry.content_md[:100000],
                    entry.content_plain[:2000],
                    entry.summary[:1000],
                    json.dumps(entry.authors, ensure_ascii=False),
                    entry.published_at,
                    entry.collected_at,
                    entry.collected_via,
                    entry.language,
                    entry.source_type,
                    entry.source_feed_url,
                    entry.source_channel,
                    entry.content_hash,
                ),
            )
            self.conn.commit()
            return True, entry.id
        except sqlite3.IntegrityError:
            # Duplicate content_hash (race condition)
            return False, entry.id

    def get_entry(self, entry_id: str) -> KnowledgeEntry | None:
        """Get a single entry by ID."""
        row = self.conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        entry = KnowledgeEntry.from_db_row(dict(row))
        entry.tags = self._get_tags(entry_id)
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID. Returns True if it existed."""
        cur = self.conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ── search ───────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KnowledgeEntry]:
        """Full-text search via FTS5. Returns entries sorted by relevance."""
        rows = self.conn.execute(
            """SELECT e.* FROM entries e
               JOIN entries_fts f ON e.rowid = f.rowid
               WHERE entries_fts MATCH ?
               ORDER BY rank
               LIMIT ? OFFSET ?""",
            (query, limit, offset),
        ).fetchall()

        results = []
        for row in rows:
            entry = KnowledgeEntry.from_db_row(dict(row))
            entry.tags = self._get_tags(entry.id)
            results.append(entry)
        return results

    def search_simple(self, query: str, limit: int = 20) -> list[KnowledgeEntry]:
        """Simple LIKE-based search (fallback when FTS5 not available)."""
        like_q = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM entries
               WHERE title LIKE ? OR content_plain LIKE ? OR summary LIKE ?
               ORDER BY collected_at DESC
               LIMIT ?""",
            (like_q, like_q, like_q, limit),
        ).fetchall()

        results = []
        for row in rows:
            entry = KnowledgeEntry.from_db_row(dict(row))
            entry.tags = self._get_tags(entry.id)
            results.append(entry)
        return results

    # ── stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return basic statistics about the knowledge base."""
        entry_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM entries"
        ).fetchone()["c"]

        tag_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM tags"
        ).fetchone()["c"]

        latest = self.conn.execute(
            "SELECT title, collected_at FROM entries ORDER BY collected_at DESC LIMIT 1"
        ).fetchone()

        # Count by collected_via
        via_rows = self.conn.execute(
            "SELECT collected_via, COUNT(*) as c FROM entries GROUP BY collected_via"
        ).fetchall()

        return {
            "entry_count": entry_count,
            "tag_count": tag_count,
            "latest_entry": dict(latest) if latest else None,
            "by_source": {r["collected_via"]: r["c"] for r in via_rows},
        }

    # ── export ───────────────────────────────────────────────────

    def export_jsonl(self, path: Path) -> int:
        """Export all entries as OKF JSONL. Returns count of exported entries."""
        rows = self.conn.execute("SELECT * FROM entries ORDER BY collected_at ASC").fetchall()
        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                entry = KnowledgeEntry.from_db_row(dict(row))
                entry.tags = self._get_tags(entry.id)
                f.write(json.dumps(entry.to_okf_dict(), ensure_ascii=False) + "\n")
                count += 1
        return count

    def import_jsonl(self, path: Path, validate: bool = True) -> dict[str, int]:
        """Import entries from an OKF JSONL file.

        Args:
            path: Path to the JSONL file.
            validate: If True, validate each entry against OKF schema before import.

        Returns:
            {imported, skipped, errors} counts.
        """
        if validate:
            from roxy.knowledge.okf_validator import validate_entry

        counts = {"imported": 0, "skipped": 0, "errors": 0}

        if not path.exists():
            logger.warning(f"Import file not found: {path}")
            return counts

        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(f"Line {line_num}: invalid JSON — {exc}")
                    counts["errors"] += 1
                    continue

                # Validate
                if validate:
                    errs = validate_entry(data)
                    if errs:
                        logger.warning(f"Line {line_num}: validation failed — {errs}")
                        counts["errors"] += 1
                        continue

                # Build entry
                entry = KnowledgeEntry(
                    id=data.get("id", ""),
                    okf_type=data.get("type", "item"),
                    title=data.get("title", ""),
                    canonical_url=data.get("canonical_url", ""),
                    content_md=data.get("content_md", ""),
                    content_plain=data.get("content_plain", ""),
                    summary=data.get("summary", ""),
                    authors=data.get("authors", []),
                    published_at=data.get("published_at", ""),
                    collected_at=data.get("collected_at", ""),
                    collected_via=data.get("collected_via", "import"),
                    language=data.get("language", "zh-CN"),
                    source_type=data.get("source", {}).get("type", ""),
                    source_feed_url=data.get("source", {}).get("feed_url", ""),
                    source_channel=data.get("source", {}).get("channel_name", ""),
                    tags=data.get("tags", []),
                    topics=data.get("topics", []),
                )

                is_new, _ = self.insert_entry(entry)
                if is_new:
                    counts["imported"] += 1
                else:
                    counts["skipped"] += 1

        return counts

    # ── helpers ──────────────────────────────────────────────────

    def _get_tags(self, entry_id: str) -> list[str]:
        rows = self.conn.execute(
            """SELECT t.name FROM tags t
               JOIN entry_tags et ON t.id = et.tag_id
               WHERE et.entry_id = ?""",
            (entry_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    def _add_tags(self, entry_id: str, tags: list[str]) -> None:
        """Add tags to an entry (idempotent on tag name)."""
        for tag in tags:
            tag = tag.strip().lower()
            if not tag or len(tag) > 100:
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,)
            )
            tag_row = self.conn.execute(
                "SELECT id FROM tags WHERE name = ?", (tag,)
            ).fetchone()
            if tag_row:
                self.conn.execute(
                    "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                    (entry_id, tag_row["id"]),
                )
        self.conn.commit()


# ── utility ──────────────────────────────────────────────────────

def _make_hash(url: str, title: str) -> str:
    """Generate a content hash for deduplication."""
    raw = f"{url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
