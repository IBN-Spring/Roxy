"""ContentCollector — run channels and feed results into KnowledgeWriter."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from roxy.config.loader import Config
from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.writer import KnowledgeWriter
from roxy.research.channels.base import Channel, ResearchItem
from roxy.research.channels import get_channel, ALL_CHANNELS

logger = logging.getLogger(__name__)


class ContentCollector:
    """Orchestrate research collection: channels → writer → store."""

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
        run_id: str = "",
    ) -> dict:
        """Collect from a channel and write to the knowledge base."""
        channel = get_channel(channel_name)
        if channel is None:
            return {
                "channel": channel_name,
                "items_found": 0, "items_new": 0, "items_duplicate": 0,
                "errors": [f"Unknown channel: '{channel_name}'"],
            }

        started_at = datetime.now(timezone.utc).isoformat()

        try:
            items = await self._run_collect(channel, feed_url, topic, since, max_items)
        except Exception as exc:
            logger.error(f"Collector: channel '{channel_name}' failed: {exc}")
            self._log_collection(run_id, channel_name, feed_url, feed_name, 0, 0, 0, str(exc), started_at)
            self._record_feed_error(feed_name, str(exc))
            return {
                "channel": channel_name,
                "items_found": 0, "items_new": 0, "items_duplicate": 0,
                "errors": [str(exc)],
            }

        item_dicts = [item.to_dict() for item in items]
        counts = self.writer.write_batch(item_dicts)

        self._log_collection(run_id, channel_name, feed_url, feed_name,
                             len(items), counts["new"], counts["duplicate"],
                             "", started_at)
        self._record_feed_success(feed_name, counts["new"])

        return {
            "channel": channel_name,
            "items_found": len(items), "items_new": counts["new"],
            "items_duplicate": counts["duplicate"], "errors": [],
        }

    async def collect_all(
        self,
        feed_url: str = "",
        topic: str = "",
        since: str | None = None,
    ) -> list[dict]:
        """Collect from ALL registered channels."""
        results = []
        for channel in ALL_CHANNELS:
            result = await self.collect(channel_name=channel.name, feed_url=feed_url,
                                        topic=topic, since=since)
            results.append(result)
        return results

    # ── run-level collection ────────────────────────────────────

    def new_run_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def collect_feeds(
        self,
        feeds: list,
        max_items: int = 50,
    ) -> dict:
        """Collect from a list of FeedSource objects. Returns a run summary.

        Returns:
            {run_id, started_at, feeds_processed, total_new, total_dup, errors, results}
        """
        run_id = self.new_run_id()
        started_at = datetime.now(timezone.utc).isoformat()
        results = []
        total_new = 0
        total_dup = 0
        errors = []

        for feed in feeds:
            try:
                result = await self.collect(
                    channel_name="rss",
                    feed_url=feed.url,
                    feed_name=feed.name,
                    run_id=run_id,
                    max_items=max_items,
                )
                results.append({
                    "feed": feed.name, "url": feed.url,
                    "items_found": result["items_found"],
                    "items_new": result["items_new"],
                    "items_duplicate": result["items_duplicate"],
                })
                total_new += result["items_new"]
                total_dup += result["items_duplicate"]
                if result.get("errors"):
                    errors.extend(result["errors"])
            except Exception as exc:
                results.append({
                    "feed": feed.name, "url": feed.url,
                    "items_found": 0, "items_new": 0, "items_duplicate": 0,
                    "error": str(exc),
                })
                errors.append(f"{feed.name}: {exc}")

        return {
            "run_id": run_id,
            "started_at": started_at,
            "feeds_processed": len(feeds),
            "total_new": total_new,
            "total_dup": total_dup,
            "errors": errors,
            "results": results,
        }

    # ── helpers ──────────────────────────────────────────────────

    async def collect_topics(self, topics: list, max_items: int = 50) -> dict:
        """Collect from a list of ResearchTopic objects across configured channels.

        Returns {run_id, topics_processed, total_new, total_dup, errors, results}.
        """
        run_id = self.new_run_id()
        started_at = datetime.now(timezone.utc).isoformat()
        results = []
        total_new = 0
        total_dup = 0
        errors = []

        for topic in topics:
            for channel_name in topic.channels:
                try:
                    result = await self.collect(
                        channel_name=channel_name,
                        topic=topic.query,
                        run_id=run_id,
                        max_items=max_items,
                    )
                    results.append({
                        "topic": topic.name, "channel": channel_name,
                        "items_found": result["items_found"],
                        "items_new": result["items_new"],
                        "items_duplicate": result["items_duplicate"],
                    })
                    total_new += result["items_new"]
                    total_dup += result["items_duplicate"]
                    if result.get("errors"):
                        errors.extend(result["errors"])
                except Exception as exc:
                    results.append({
                        "topic": topic.name, "channel": channel_name,
                        "items_found": 0, "items_new": 0, "items_duplicate": 0,
                        "error": str(exc),
                    })
                    errors.append(f"{topic.name}/{channel_name}: {exc}")

            # Track topic state
            topic_errors = [e for e in errors if topic.name in e]
            if topic_errors:
                self._record_topic_error(topic.name, topic_errors[0])
            else:
                topic_new = sum(r["items_new"] for r in results if r["topic"] == topic.name)
                self._record_topic_success(topic.name, topic_new)

        return {
            "run_id": run_id, "started_at": started_at,
            "topics_processed": len(topics),
            "total_new": total_new, "total_dup": total_dup,
            "errors": errors, "results": results,
        }

    def _record_topic_success(self, topic_name: str, new_count: int) -> None:
        if not topic_name:
            return
        try:
            from roxy.research.topic_manager import TopicManager
            TopicManager(self.config).record_success(topic_name, new_count)
        except Exception as exc:
            logger.warning(f"Failed to record topic success: {exc}")

    def _record_topic_error(self, topic_name: str, error_msg: str) -> None:
        if not topic_name:
            return
        try:
            from roxy.research.topic_manager import TopicManager
            TopicManager(self.config).record_error(topic_name, error_msg)
        except Exception as exc:
            logger.warning(f"Failed to record topic error: {exc}")

    async def _run_collect(self, channel, feed_url, topic, since, max_items):
        try:
            return await channel.collect(self.config, topic=topic, since=since,
                                         feed_url=feed_url, max_items=max_items)
        except TypeError:
            return await channel.collect(self.config, topic=topic, since=since)

    def _record_feed_success(self, feed_name, new_count):
        if not feed_name:
            return
        try:
            from roxy.research.source_manager import SourceManager
            SourceManager(self.config).record_success(feed_name, new_count)
        except Exception as exc:
            logger.warning(f"Failed to record feed success for '{feed_name}': {exc}")

    def _record_feed_error(self, feed_name, error_msg):
        if not feed_name:
            return
        try:
            from roxy.research.source_manager import SourceManager
            SourceManager(self.config).record_error(feed_name, error_msg)
        except Exception as exc:
            logger.warning(f"Failed to record feed error for '{feed_name}': {exc}")

    def _log_collection(self, run_id, channel_name, feed_url, source_name,
                        found, new, dup, errors, started_at):
        try:
            self.store.conn.execute(
                """INSERT INTO collection_log (
                    run_id, channel_name, source_name, feed_url,
                    items_found, items_new, items_duplicate,
                    errors, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, channel_name, source_name, feed_url,
                 found, new, dup, errors, started_at,
                 datetime.now(timezone.utc).isoformat()),
            )
            self.store.conn.commit()
        except Exception as exc:
            logger.warning(f"Failed to write collection log: {exc}")
