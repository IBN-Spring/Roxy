"""Tests for SourceManager — feed CRUD in config."""

from roxy.config.loader import Config
from roxy.research.source_manager import SourceManager, FeedSource


class TestFeedSource:
    def test_to_dict(self):
        fs = FeedSource(name="Test", url="https://example.com/rss")
        d = fs.to_dict()
        assert d["name"] == "Test"
        assert d["url"] == "https://example.com/rss"
        assert d["enabled"] is True

    def test_from_dict(self):
        d = {"name": "X", "url": "https://x.com", "enabled": False}
        fs = FeedSource.from_dict(d)
        assert fs.name == "X"
        assert not fs.enabled


class TestSourceManager:
    def test_list_empty(self, config: Config):
        config.load()
        sm = SourceManager(config)
        feeds = sm.list_feeds()
        assert feeds == []

    def test_add_and_list(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("My Feed", "https://example.com/rss")
        feeds = sm.list_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "My Feed"

    def test_add_duplicate_url_raises(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("F1", "https://example.com/rss")
        try:
            sm.add_feed("F2", "https://example.com/rss")
            assert False, "Should have raised"
        except ValueError as exc:
            assert "already exists" in str(exc)

    def test_remove_existing(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("ToRemove", "https://example.com/rm")
        assert sm.remove_feed("ToRemove")
        assert sm.list_feeds() == []

    def test_remove_nonexistent(self, config: Config):
        config.load()
        sm = SourceManager(config)
        assert not sm.remove_feed("nope")

    def test_set_enabled(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Toggle", "https://example.com/toggle")
        sm.set_enabled("Toggle", False)
        feeds = sm.list_feeds()
        assert not feeds[0].enabled

        sm.set_enabled("Toggle", True)
        assert sm.list_feeds()[0].enabled

    def test_list_enabled_only(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("On", "https://on.com")
        sm.add_feed("Off", "https://off.com")
        sm.set_enabled("Off", False)

        enabled = sm.list_feeds(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "On"

    def test_persists_across_config_reload(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Persist", "https://example.com/persist")

        # Reload config from file
        cfg2 = Config(path=config._path)
        cfg2.load()
        sm2 = SourceManager(cfg2)
        feeds = sm2.list_feeds()
        assert len(feeds) >= 1
        assert any(f.name == "Persist" for f in feeds)
