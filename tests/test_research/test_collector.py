"""Tests for ContentCollector — RSS → writer → store pipeline."""

from pathlib import Path

import pytest

from roxy.config.loader import Config
from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.query import KnowledgeQuery
from roxy.research.collector import ContentCollector


# ── helpers ─────────────────────────────────────────────────────

def _mock_rss_collect(items):
    """Create a mock RSSChannel.collect that returns given items."""
    async def _collect(self, config, topic="", since=None, feed_url="", max_items=50):
        from roxy.research.channels.base import ResearchItem
        return [
            ResearchItem(
                title=it["title"],
                canonical_url=it["url"],
                content_plain=it.get("content", ""),
                summary=it.get("summary", ""),
                collected_via="rss",
                source_feed_url=feed_url,
                source_channel="Mock Feed",
                published_at=it.get("published_at", ""),
            )
            for it in items
        ]
    return _collect


# ── tests ───────────────────────────────────────────────────────

class TestContentCollector:
    @pytest.mark.asyncio
    async def test_collect_rss_writes_to_store(self, tmp_path: Path, monkeypatch):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        cfg = Config()
        cfg.load()

        collector = ContentCollector(cfg, store)

        # Mock the RSS channel's collect method
        from roxy.research.channels.rss import RSSChannel
        original_collect = RSSChannel.collect
        monkeypatch.setattr(
            RSSChannel, "collect",
            _mock_rss_collect([
                {"title": "RSS Item 1", "url": "https://example.com/rss1", "content": "hello world"},
                {"title": "RSS Item 2", "url": "https://example.com/rss2", "content": "goodbye"},
            ]),
        )

        try:
            result = await collector.collect(
                channel_name="rss",
                feed_url="https://example.com/feed.xml",
            )
        finally:
            monkeypatch.setattr(RSSChannel, "collect", original_collect)

        assert result["items_found"] == 2
        assert result["items_new"] == 2
        assert result["items_duplicate"] == 0
        assert result["channel"] == "rss"

        # Verify items are in the store
        q = KnowledgeQuery(store)
        results = q.search("hello")
        assert len(results) >= 1
        assert any(r.title == "RSS Item 1" for r in results)

    @pytest.mark.asyncio
    async def test_collect_dedup_across_runs(self, tmp_path: Path, monkeypatch):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        cfg = Config()
        cfg.load()
        collector = ContentCollector(cfg, store)

        items = [
            {"title": "Unique", "url": "https://example.com/u1", "content": "unique content"},
        ]

        from roxy.research.channels.rss import RSSChannel
        orig = RSSChannel.collect

        # First run
        monkeypatch.setattr(RSSChannel, "collect", _mock_rss_collect(items))
        r1 = await collector.collect(channel_name="rss", feed_url="https://example.com/feed")
        assert r1["items_new"] == 1

        # Second run — same items
        r2 = await collector.collect(channel_name="rss", feed_url="https://example.com/feed")
        assert r2["items_new"] == 0
        assert r2["items_duplicate"] == 1

        monkeypatch.setattr(RSSChannel, "collect", orig)

    @pytest.mark.asyncio
    async def test_collect_unknown_channel(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        cfg = Config()
        cfg.load()
        collector = ContentCollector(cfg, store)

        result = await collector.collect(channel_name="nonexistent")
        assert result["items_found"] == 0
        assert len(result["errors"]) > 0
