"""Tests for KnowledgeStore — init, insert, search, stats, export."""

import json
from pathlib import Path

from roxy.knowledge.schema import KnowledgeEntry
from roxy.knowledge.store import KnowledgeStore


class TestKnowledgeStore:
    def test_init_db_creates_tables(self, tmp_path: Path):
        db = tmp_path / "test.db"
        store = KnowledgeStore(db_path=db)
        store.init_db()
        # Verify tables exist
        tables = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "entries" in table_names
        assert "tags" in table_names

    def test_insert_entry(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        entry = KnowledgeEntry(
            title="Test Article",
            canonical_url="https://example.com/1",
            content_plain="This is test content.",
            summary="A test summary.",
            collected_via="rss",
            source_feed_url="https://example.com/feed",
            source_channel="Example Blog",
        )

        is_new, entry_id = store.insert_entry(entry)
        assert is_new
        assert entry_id

        # Verify we can read it back
        loaded = store.get_entry(entry_id)
        assert loaded is not None
        assert loaded.title == "Test Article"
        assert loaded.canonical_url == "https://example.com/1"

    def test_dedup_by_content_hash(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        entry1 = KnowledgeEntry(
            title="Dup Article",
            canonical_url="https://example.com/dup",
            content_plain="dup",
        )
        is_new1, id1 = store.insert_entry(entry1)
        assert is_new1

        # Same URL + title → same hash → duplicate
        entry2 = KnowledgeEntry(
            title="Dup Article",
            canonical_url="https://example.com/dup",
            content_plain="different content",
        )
        is_new2, id2 = store.insert_entry(entry2)
        assert not is_new2
        assert id2 == id1  # Same ID returned

    def test_search_fts5(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="Protein Folding Advances",
            canonical_url="https://example.com/pf",
            content_plain="New research on protein folding.",
            summary="Protein folding breakthroughs.",
        ))
        store.insert_entry(KnowledgeEntry(
            title="Drug Design Methods",
            canonical_url="https://example.com/dd",
            content_plain="Computational drug design methods.",
            summary="Drug design review.",
        ))

        results = store.search("protein")
        assert len(results) >= 1
        assert any("protein" in r.title.lower() or "protein" in r.content_plain.lower() for r in results)

    def test_search_simple_fallback(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="Quantum Computing",
            canonical_url="https://example.com/qc",
            content_plain="Quantum computing explained.",
        ))

        results = store.search_simple("quantum")
        assert len(results) >= 1

    def test_get_stats(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="S1", canonical_url="https://a.com/1", content_plain="a",
            collected_via="rss",
        ))
        store.insert_entry(KnowledgeEntry(
            title="S2", canonical_url="https://a.com/2", content_plain="b",
            collected_via="web",
        ))

        stats = store.get_stats()
        assert stats["entry_count"] == 2
        assert stats["by_source"]["rss"] == 1
        assert stats["by_source"]["web"] == 1

    def test_export_jsonl(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        store.insert_entry(KnowledgeEntry(
            title="Export Test",
            canonical_url="https://example.com/export",
            content_plain="export me",
        ))

        export_path = tmp_path / "export.jsonl"
        count = store.export_jsonl(export_path)
        assert count == 1

        with open(export_path, "r") as f:
            line = f.readline()
        data = json.loads(line)
        assert data["title"] == "Export Test"

    def test_delete_entry(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        _, eid = store.insert_entry(KnowledgeEntry(
            title="Delete Me", canonical_url="https://example.com/del", content_plain="x",
        ))
        assert store.delete_entry(eid)
        assert store.get_entry(eid) is None
        assert not store.delete_entry("nonexistent")

    def test_add_tags(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()

        _, eid = store.insert_entry(KnowledgeEntry(
            title="Tagged", canonical_url="https://example.com/tag", content_plain="x",
        ))
        store._add_tags(eid, ["ai", "biology", "AI"])  # duplicate case insensitivity
        tags = store._get_tags(eid)
        assert "ai" in tags
        assert "biology" in tags
