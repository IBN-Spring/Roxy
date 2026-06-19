"""Tests for KnowledgeQuery — search with filters."""

from pathlib import Path

from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.query import KnowledgeQuery


class TestKnowledgeQuery:
    def test_search_returns_results(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        store.insert_entry(KnowledgeEntry(
            title="AlphaFold 3", canonical_url="https://a.com/af3",
            content_plain="AlphaFold 3 protein structure prediction.",
            collected_via="rss",
        ))

        q = KnowledgeQuery(store)
        results = q.search("AlphaFold")
        assert len(results) >= 1

    def test_filter_by_tag(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        _, eid1 = store.insert_entry(KnowledgeEntry(
            title="AI Paper", canonical_url="https://a.com/ai",
            content_plain="AI research.", collected_via="rss",
        ))
        store._add_tags(eid1, ["ai"])

        _, eid2 = store.insert_entry(KnowledgeEntry(
            title="Bio Paper", canonical_url="https://a.com/bio",
            content_plain="Bio research.", collected_via="rss",
        ))
        store._add_tags(eid2, ["biology"])

        q = KnowledgeQuery(store)
        results = q.search("research", tag="ai")
        assert len(results) >= 1
        assert all("ai" in [t.lower() for t in r.tags] for r in results)

    def test_filter_by_collected_via(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        store.insert_entry(KnowledgeEntry(
            title="RSS Item", canonical_url="https://a.com/rss1",
            content_plain="rss content", collected_via="rss",
        ))
        store.insert_entry(KnowledgeEntry(
            title="Web Item", canonical_url="https://a.com/web1",
            content_plain="web content", collected_via="web",
        ))

        q = KnowledgeQuery(store)
        results = q.search("content", collected_via="rss")
        assert all(r.collected_via == "rss" for r in results)

    def test_list_recent(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        store.insert_entry(KnowledgeEntry(
            title="R1", canonical_url="https://a.com/r1", content_plain="x",
        ))

        q = KnowledgeQuery(store)
        results = q.list_recent(limit=5)
        assert len(results) >= 1

    def test_get_by_url(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        store.insert_entry(KnowledgeEntry(
            title="URL Lookup", canonical_url="https://example.com/lookup",
            content_plain="find me",
        ))

        q = KnowledgeQuery(store)
        entry = q.get_by_url("https://example.com/lookup")
        assert entry is not None
        assert entry.title == "URL Lookup"

        assert q.get_by_url("https://no-match.com") is None
