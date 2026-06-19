"""KnowledgeWriter — deduplicate and persist research items."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)


class KnowledgeWriter:
    """Writes research items to the knowledge base with deduplication.

    Usage:
        store = KnowledgeStore()
        store.init_db()
        writer = KnowledgeWriter(store)
        is_new, entry_id = writer.write(item_dict)
    """

    def __init__(self, store: KnowledgeStore | None = None):
        self.store = store or KnowledgeStore()

    def write(self, item: dict[str, Any]) -> tuple[bool, str]:
        """Write a research item to the KB. Returns (is_new, entry_id).

        Deduplication:
        1. content_hash = SHA256(canonical_url + title) — primary dedup key
        2. canonical_url — checked before hashing (cheap pre-filter)

        Args:
            item: Dict with at minimum 'title' and 'canonical_url'.
                  Optional: content_md, content_plain, summary, authors,
                            published_at, collected_via, tags, source_type,
                            source_feed_url, source_channel, language.
        """
        url = item.get("canonical_url", "").strip()
        title = item.get("title", "").strip()

        if not url or not title:
            logger.warning(f"KnowledgeWriter: skipping item with missing url/title: {item}")
            return False, ""

        # Pre-filter: check URL (cheap)
        existing = self.store.conn.execute(
            "SELECT id FROM entries WHERE canonical_url = ?",
            (url,),
        ).fetchone()
        if existing:
            return False, existing["id"]

        # Build content hash
        content_hash = _make_hash(url, title)

        entry = KnowledgeEntry(
            title=title,
            canonical_url=url,
            okf_type=item.get("type", "item"),
            content_md=item.get("content_md", ""),
            content_plain=item.get("content_plain", ""),
            summary=item.get("summary", ""),
            authors=item.get("authors", []),
            published_at=item.get("published_at", ""),
            collected_at=item.get("collected_at", datetime.now(timezone.utc).isoformat()),
            collected_via=item.get("collected_via", "manual"),
            language=item.get("language", "zh-CN"),
            source_type=item.get("source_type", ""),
            source_feed_url=item.get("source_feed_url", ""),
            source_channel=item.get("source_channel", ""),
            content_hash=content_hash,
            tags=item.get("tags", []),
            topics=item.get("topics", []),
        )

        is_new, entry_id = self.store.insert_entry(entry)

        # Add tags
        if is_new and entry.tags:
            self.store._add_tags(entry_id, entry.tags)

        return is_new, entry_id

    def write_batch(self, items: list[dict[str, Any]]) -> dict[str, int]:
        """Write a batch of items. Returns {new, duplicate, error} counts."""
        counts = {"new": 0, "duplicate": 0, "error": 0}
        for item in items:
            try:
                is_new, _ = self.write(item)
                if is_new:
                    counts["new"] += 1
                else:
                    counts["duplicate"] += 1
            except Exception as exc:
                logger.error(f"KnowledgeWriter: error writing item: {exc}")
                counts["error"] += 1
        return counts


def _make_hash(url: str, title: str) -> str:
    raw = f"{url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
