"""KnowledgeQuery — full-text search and filtering."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore


class KnowledgeQuery:
    """Query the knowledge base with search, filter, and pagination."""

    def __init__(self, store: KnowledgeStore | None = None):
        self.store = store or KnowledgeStore()

    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        tag: str | None = None,
        collected_via: str | None = None,
        since: str | None = None,
    ) -> list[KnowledgeEntry]:
        """Full-text search with optional filters.

        Args:
            query: FTS5 query string.
            limit, offset: Pagination.
            tag: Filter by tag name.
            collected_via: Filter by source channel (e.g. "rss", "web").
            since: ISO 8601 date string — only return entries collected after this.
        """
        # Use FTS5 when it's a meaningful query, else fall back to simple LIKE
        if query.strip():
            try:
                results = self.store.search(query, limit=limit, offset=offset)
            except Exception:
                results = self.store.search_simple(query, limit=limit)
        else:
            results = self._list_recent(limit=limit)

        # Post-filter
        if tag:
            results = [e for e in results if tag.lower() in [t.lower() for t in e.tags]]
        if collected_via:
            results = [e for e in results if e.collected_via == collected_via]
        if since:
            results = [e for e in results if e.collected_at >= since]

        return results

    def list_recent(self, limit: int = 20) -> list[KnowledgeEntry]:
        """Return the most recently collected entries."""
        return self._list_recent(limit=limit)

    def get_by_url(self, url: str) -> KnowledgeEntry | None:
        """Find an entry by its canonical URL (exact match)."""
        row = self.store.conn.execute(
            "SELECT id FROM entries WHERE canonical_url = ? LIMIT 1",
            (url.strip(),),
        ).fetchone()
        if row:
            return self.store.get_entry(row["id"])
        return None

    # ── helpers ──────────────────────────────────────────────────

    def _list_recent(self, limit: int = 20) -> list[KnowledgeEntry]:
        rows = self.store.conn.execute(
            "SELECT * FROM entries ORDER BY collected_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for row in rows:
            entry = KnowledgeEntry.from_db_row(dict(row))
            entry.tags = self.store._get_tags(entry.id)
            results.append(entry)
        return results
