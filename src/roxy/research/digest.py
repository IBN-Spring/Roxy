"""ResearchDigest — summarise recent knowledge base entries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from roxy.knowledge.query import KnowledgeQuery
from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore


class ResearchDigest:
    """Generate a digest of recent research findings."""

    def __init__(self, store: KnowledgeStore | None = None):
        self.store = store or KnowledgeStore()
        self.store.init_db()
        self.query = KnowledgeQuery(self.store)

    def generate(
        self,
        days: int = 7,
        limit: int = 50,
        collected_via: str | None = None,
    ) -> dict:
        """Generate a digest of recent KB entries.

        Args:
            days: Look back this many days.
            limit: Max entries to include.
            collected_via: Optional filter by source channel.

        Returns:
            Dict with {period, generated_at, entry_count, entries, summary_text}.
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get recent entries
        entries = self.query.search(
            query="",
            limit=limit,
            since=since,
            collected_via=collected_via,
        )
        # search with empty query just lists recent
        if not entries:
            entries = self._fallback_recent(limit, since, collected_via)

        # Group by source
        by_source: dict[str, list[KnowledgeEntry]] = {}
        for e in entries:
            source = e.collected_via or "unknown"
            by_source.setdefault(source, []).append(e)

        # Group by date
        by_date: dict[str, list[KnowledgeEntry]] = {}
        for e in entries:
            date_key = e.collected_at[:10] if e.collected_at else "unknown"
            by_date.setdefault(date_key, []).append(e)

        # Build summary text
        summary_lines = [
            f"Research Digest — {days}-day summary",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Entries: {len(entries)}",
            "",
        ]

        for source, items in sorted(by_source.items()):
            summary_lines.append(f"## {source} ({len(items)} items)")
            for item in items[:10]:  # top 10 per source
                date = item.published_at[:10] if item.published_at else "—"
                title = item.title or "(untitled)"
                summary_lines.append(f"- [{date}] {title}")
                if item.canonical_url:
                    summary_lines.append(f"  {item.canonical_url}")
            summary_lines.append("")

        return {
            "period_days": days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(entries),
            "entries": [e.to_okf_dict() for e in entries],
            "by_source": {k: len(v) for k, v in by_source.items()},
            "by_date": {k: len(v) for k, v in by_date.items()},
            "summary_text": "\n".join(summary_lines),
        }

    def _fallback_recent(
        self, limit: int, since: str, collected_via: str | None
    ) -> list[KnowledgeEntry]:
        """Fallback: list recent entries when FTS5 search returns nothing."""
        entries = self.query.list_recent(limit=limit)
        # Filter manually
        filtered = []
        for e in entries:
            if e.collected_at < since:
                continue
            if collected_via and e.collected_via != collected_via:
                continue
            filtered.append(e)
        return filtered
