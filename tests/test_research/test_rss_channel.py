"""Tests for RSSChannel — feed parsing, date handling, ResearchItem output."""

import pytest

from roxy.research.channels.rss import RSSChannel


# ── mock feed ───────────────────────────────────────────────────

def _mock_feed(entries: list[dict] | None = None, feed_title: str = "Test Feed"):
    """Build a feedparser-like feed object."""
    from types import SimpleNamespace

    feed = SimpleNamespace()
    feed.feed = {"title": feed_title}
    feed.bozo = False
    feed.bozo_exception = None
    feed.entries = []

    for i, e in enumerate(entries or []):
        ns = SimpleNamespace()
        ns.title = e.get("title", f"Entry {i}")
        ns.link = e.get("link", f"https://example.com/{i}")
        ns.summary = e.get("summary", f"Summary {i}")
        ns.published = e.get("published", "2025-01-15T00:00:00Z")
        ns.published_parsed = e.get("published_parsed", None)
        ns.updated = e.get("updated", "")
        ns.updated_parsed = e.get("updated_parsed", None)
        ns.authors = e.get("authors", [])
        ns.author = e.get("author", "")
        feed.entries.append(ns)

    return feed


# ── tests ───────────────────────────────────────────────────────

class TestRSSChannel:
    @pytest.mark.asyncio
    async def test_check_ok(self):
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()
        status, _ = await ch.check(cfg)
        assert status in ("ok", "off")

    @pytest.mark.asyncio
    async def test_collect_empty_feed(self, monkeypatch):
        """Empty feed returns empty list."""
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()

        monkeypatch.setattr(
            "feedparser.parse",
            lambda url: _mock_feed([]),
        )

        items = await ch.collect(cfg, feed_url="https://example.com/feed")
        assert items == []

    @pytest.mark.asyncio
    async def test_collect_returns_research_items(self, monkeypatch):
        """A feed with 2 entries returns 2 ResearchItems."""
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()

        monkeypatch.setattr(
            "feedparser.parse",
            lambda url: _mock_feed([
                {
                    "title": "Article 1",
                    "link": "https://example.com/1",
                    "summary": "Content one.",
                    "authors": [{"name": "Alice"}],
                },
                {
                    "title": "Article 2",
                    "link": "https://example.com/2",
                    "summary": "Content two.",
                    "authors": [{"name": "Bob"}],
                },
            ]),
        )

        items = await ch.collect(cfg, feed_url="https://example.com/feed")
        assert len(items) == 2
        assert items[0].title == "Article 1"
        assert items[0].canonical_url == "https://example.com/1"
        assert items[0].collected_via == "rss"
        assert items[0].source_feed_url == "https://example.com/feed"
        assert items[0].source_channel == "Test Feed"
        assert "Alice" in items[0].authors

    @pytest.mark.asyncio
    async def test_collect_respects_max_items(self, monkeypatch):
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()

        entries = [
            {"title": f"E{i}", "link": f"https://x.com/{i}"}
            for i in range(20)
        ]
        monkeypatch.setattr("feedparser.parse", lambda url: _mock_feed(entries))

        items = await ch.collect(cfg, feed_url="https://x.com/feed", max_items=5)
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_no_feed_url_returns_empty(self):
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()
        items = await ch.collect(cfg, feed_url="")
        assert items == []

    @pytest.mark.asyncio
    async def test_malformed_feed_returns_empty(self, monkeypatch):
        ch = RSSChannel()
        from roxy.config.loader import Config
        cfg = Config()
        cfg.load()

        def bad_parse(url):
            raise RuntimeError("parse failure")

        monkeypatch.setattr("feedparser.parse", bad_parse)

        items = await ch.collect(cfg, feed_url="https://broken.com/feed")
        assert items == []
