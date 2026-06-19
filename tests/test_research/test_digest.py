"""Tests for ResearchDigest — summarizing recent KB entries."""

from pathlib import Path

from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore
from roxy.research.digest import ResearchDigest


class TestResearchDigest:
    def test_empty_kb_returns_zero_entries(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        dg = ResearchDigest(store)
        result = dg.generate(days=7)
        assert result["entry_count"] == 0

    def test_digest_includes_recent_entries(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="Recent Article",
            canonical_url="https://example.com/recent",
            content_plain="Recent research finding.",
            collected_via="rss",
        ))

        dg = ResearchDigest(store)
        result = dg.generate(days=30)
        assert result["entry_count"] >= 1
        assert "Recent Article" in result["summary_text"]

    def test_digest_groups_by_source(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="RSS Item", canonical_url="https://a.com/rss",
            content_plain="x", collected_via="rss",
        ))
        store.insert_entry(KnowledgeEntry(
            title="Web Item", canonical_url="https://a.com/web",
            content_plain="y", collected_via="web",
        ))

        dg = ResearchDigest(store)
        result = dg.generate(days=30)
        assert "rss" in result["by_source"]
        assert "web" in result["by_source"]

    def test_filter_by_source(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="RSS Only", canonical_url="https://a.com/1",
            content_plain="rss entry", collected_via="rss",
        ))
        store.insert_entry(KnowledgeEntry(
            title="Web Item", canonical_url="https://a.com/2",
            content_plain="web entry", collected_via="web",
        ))

        dg = ResearchDigest(store)
        result = dg.generate(days=30, collected_via="rss")
        assert result["entry_count"] >= 1
        assert "RSS Only" in result["summary_text"]
