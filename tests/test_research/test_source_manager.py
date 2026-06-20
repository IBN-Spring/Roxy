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

    def test_has_id(self):
        fs = FeedSource(name="T", url="https://t.com")
        assert fs.id
        assert len(fs.id) == 12

    def test_state_fields(self):
        fs = FeedSource(name="S", url="https://s.com", tags=["ai"], total_collected=42)
        d = fs.to_dict()
        assert d["tags"] == ["ai"]
        assert d["total_collected"] == 42
        assert d["last_run_at"] == ""
        assert d["last_error"] == ""

    def test_has_error(self):
        fs = FeedSource(name="E", url="https://e.com")
        assert not fs.has_error
        fs.last_error = "timeout"
        assert fs.has_error

    def test_from_dict_with_state(self):
        d = {
            "name": "Full", "url": "https://f.com", "enabled": True,
            "id": "abc123def456", "tags": ["science"],
            "last_run_at": "2025-01-01T00:00:00",
            "last_success_at": "2025-01-01T00:00:01",
            "last_error": "timeout", "total_collected": 10,
        }
        fs = FeedSource.from_dict(d)
        assert fs.id == "abc123def456"
        assert fs.tags == ["science"]
        assert fs.total_collected == 10
        assert fs.has_error


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

    # ── state tracking ────────────────────────────────────────

    def test_record_run_updates_last_run(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Runner", "https://r.com")
        sm.record_run("Runner")
        feed = sm.get_feed("Runner")
        assert feed is not None
        assert feed.last_run_at

    def test_record_success_updates_state(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Success", "https://s.com")
        sm.record_success("Success", 5)
        feed = sm.get_feed("Success")
        assert feed.last_success_at
        assert feed.total_collected == 5
        assert not feed.has_error

    def test_record_error_updates_state(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Failer", "https://f.com")
        sm.record_error("Failer", "Connection refused")
        feed = sm.get_feed("Failer")
        assert feed.has_error
        assert "Connection refused" in feed.last_error

    def test_record_success_clears_error(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("Recover", "https://r.com")
        sm.record_error("Recover", "old error")
        sm.record_success("Recover", 3)
        feed = sm.get_feed("Recover")
        assert not feed.has_error
        assert feed.total_collected == 3

    def test_get_status_summary(self, config: Config):
        config.load()
        sm = SourceManager(config)
        sm.add_feed("A", "https://a.com")
        sm.add_feed("B", "https://b.com")
        sm.set_enabled("B", False)
        sm.record_error("A", "fail")
        summary = sm.get_status_summary()
        assert summary["total"] == 2
        assert summary["enabled"] == 1
        assert summary["with_errors"] == 1
