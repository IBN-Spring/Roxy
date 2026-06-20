"""ContentCollector — run channels and feed results into KnowledgeWriter."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from roxy.config.loader import Config
from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.writer import KnowledgeWriter
from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels import get_channel, ALL_CHANNELS

logger = logging.getLogger(__name__)


class ContentCollector:
    """Orchestrate research collection: channels → writer → store.

    Usage:
        collector = ContentCollector(config)
        result = await collector.collect(channel_name="rss", feed_url="https://...")
    """

    def __init__(self, config: Config, store: KnowledgeStore | None = None):
        self.config = config
        self.store = store or KnowledgeStore()
        self.store.init_db()
        self.writer = KnowledgeWriter(self.store)

    async def collect(
        self,
        channel_name: str,
        feed_url: str = "",
        topic: str = "",
        since: str | None = None,
        max_items: int = 50,
        feed_name: str = "",
    ) -> dict:
        """Collect from a channel and write to the knowledge base.

        Args:
            channel_name: Which channel to use ("rss", "web", etc.).
            feed_url: Feed URL or search URL for the channel.
            topic: Optional topic filter.
            since: ISO 8601 — only collect items published after this.
            max_items: Max items to fetch.
            feed_name: Optional feed name for state tracking.
        """
        channel = get_channel(channel_name)
        if channel is None:
            return {
                "channel": channel_name,
                "items_found": 0,
                "items_new": 0,
                "items_duplicate": 0,
                "errors": [f"Unknown channel: '{channel_name}'"],
            }

        started_at = datetime.now(timezone.utc).isoformat()

        # Collect
        try:
            items = await self._run_collect(channel, feed_url, topic, since, max_items)
        except Exception as exc:
            logger.error(f"Collector: channel '{channel_name}' failed: {exc}")
            self._log_collection(channel_name, feed_url, 0, 0, 0, str(exc), started_at)
            self._record_feed_error(feed_name, str(exc))
            return {
                "channel": channel_name,
                "items_found": 0,
                "items_new": 0,
                "items_duplicate": 0,
                "errors": [str(exc)],
            }

        # Write to KB
        item_dicts = [item.to_dict() for item in items]
        counts = self.writer.write_batch(item_dicts)

        self._log_collection(
            channel_name, feed_url,
            len(items), counts["new"], counts["duplicate"],
            "",  # no errors
            started_at,
        )

        # Track source state
        self._record_feed_success(feed_name, counts["new"])

        return {
            "channel": channel_name,
            "items_found": len(items),
            "items_new": counts["new"],
            "items_duplicate": counts["duplicate"],
            "errors": [],
        }

    async def collect_all(
        self,
        feed_url: str = "",
        topic: str = "",
        since: str | None = None,
    ) -> list[dict]:
        """Collect from ALL registered channels. Returns per-channel results."""
        results = []
        for channel in ALL_CHANNELS:
            result = await self.collect(
                channel_name=channel.name,
                feed_url=feed_url,
                topic=topic,
                since=since,
            )
            results.append(result)
        return results

    # ── helpers ──────────────────────────────────────────────────

    async def _run_collect(
        self,
        channel: Channel,
        feed_url: str,
        topic: str,
        since: str | None,
        max_items: int,
    ) -> list[ResearchItem]:
        """Dispatch to the channel's collect().

        Passes config as positional arg so both bound methods and monkeypatched
        standalone functions work correctly.
        """
        try:
            return await channel.collect(
                self.config,
                topic=topic,
                since=since,
                feed_url=feed_url,
                max_items=max_items,
            )
        except TypeError:
            # Channel doesn't accept feed_url/max_items — retry without them
            return await channel.collect(
                self.config,
                topic=topic,
                since=since,
            )

    def _record_feed_success(self, feed_name: str, new_count: int) -> None:
        """Update source state after successful collection."""
        if not feed_name:
            return
        try:
            from roxy.research.source_manager import SourceManager
            sm = SourceManager(self.config)
            sm.record_success(feed_name, new_count)
        except Exception as exc:
            logger.warning(f"Failed to record feed success for '{feed_name}': {exc}")

    def _record_feed_error(self, feed_name: str, error_msg: str) -> None:
        """Update source state after failed collection."""
        if not feed_name:
            return
        try:
            from roxy.research.source_manager import SourceManager
            sm = SourceManager(self.config)
            sm.record_error(feed_name, error_msg)
        except Exception as exc:
            logger.warning(f"Failed to record feed error for '{feed_name}': {exc}")

    def _log_collection(
        self,
        channel_name: str,
        feed_url: str,
        found: int,
        new: int,
        dup: int,
        errors: str,
        started_at: str,
    ) -> None:
        """Write a collection log entry."""
        try:
            self.store.conn.execute(
                """INSERT INTO collection_log (
                    channel_name, feed_url, items_found, items_new,
                    items_duplicate, errors, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    channel_name,
                    feed_url,
                    found,
                    new,
                    dup,
                    errors,
                    started_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.store.conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to write collection log: {exc}")
