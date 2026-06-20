"""Tests for the monitor CLI."""

from click.testing import CliRunner

from roxy.cli.monitor_cmd import monitor_cmd


class FakeFeed:
    name = "Broken Feed"
    url = "https://example.com/rss"


def test_monitor_run_json_exits_nonzero_on_collection_error(monkeypatch):
    """Cron-friendly JSON mode should still fail when collection has errors."""

    class FakeSourceManager:
        def __init__(self, config):
            pass
        def list_feeds(self, enabled_only=False):
            return [FakeFeed()]

    class FakeTopicManager:
        def __init__(self, config):
            pass
        def list_topics(self, enabled_only=False):
            return []

    class FakeContentCollector:
        def __init__(self, config):
            pass
        async def collect(self, **kwargs):
            return {
                "items_found": 0, "items_new": 0, "items_duplicate": 0,
                "errors": ["feed unavailable"],
            }

    monkeypatch.setattr("roxy.research.source_manager.SourceManager", FakeSourceManager)
    monkeypatch.setattr("roxy.research.topic_manager.TopicManager", FakeTopicManager)
    monkeypatch.setattr("roxy.research.collector.ContentCollector", FakeContentCollector)

    result = CliRunner().invoke(monitor_cmd, ["run", "--json"])

    assert result.exit_code == 1
    assert '"status": "partial"' in result.output
    assert "feed unavailable" in result.output

def test_monitor_run_feeds_only(monkeypatch):
    """--feeds-only skips topics."""

    class FakeSourceManager:
        def __init__(self, config): pass
        def list_feeds(self, enabled_only=False):
            return [FakeFeed()]

    class FakeTopicManager:
        def __init__(self, config):
            raise AssertionError("Should not be called")
        def list_topics(self, enabled_only=False): pass

    class FakeContentCollector:
        def __init__(self, config): pass
        async def collect(self, **kwargs):
            return {"items_found": 1, "items_new": 1, "items_duplicate": 0, "errors": []}

    monkeypatch.setattr("roxy.research.source_manager.SourceManager", FakeSourceManager)
    monkeypatch.setattr("roxy.research.topic_manager.TopicManager", FakeTopicManager)
    monkeypatch.setattr("roxy.research.collector.ContentCollector", FakeContentCollector)

    result = CliRunner().invoke(monitor_cmd, ["run", "--feeds-only"])
    assert result.exit_code == 0
    assert "1 new" in result.output or "complete" in result.output.lower()
