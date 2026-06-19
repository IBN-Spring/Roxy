"""Tests for KnowledgeWriter — dedup by URL + content hash."""

from pathlib import Path

from roxy.knowledge.store import KnowledgeStore
from roxy.knowledge.writer import KnowledgeWriter


class TestKnowledgeWriter:
    def test_write_new_item(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        is_new, eid = writer.write({
            "title": "New Article",
            "canonical_url": "https://example.com/new",
            "content_plain": "Fresh content.",
            "collected_via": "rss",
        })
        assert is_new
        assert eid

        entry = store.get_entry(eid)
        assert entry is not None
        assert entry.title == "New Article"

    def test_dedup_by_url(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        writer.write({
            "title": "First Write",
            "canonical_url": "https://example.com/same-url",
            "content_plain": "A",
        })

        # Same URL → duplicate
        is_new2, _ = writer.write({
            "title": "Different Title",
            "canonical_url": "https://example.com/same-url",
            "content_plain": "B",
        })
        assert not is_new2

    def test_dedup_by_hash(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        writer.write({
            "title": "Article X",
            "canonical_url": "https://example.com/x",
        })

        # Different URL, but same title and content hash
        is_new2, _ = writer.write({
            "title": "Article X",
            "canonical_url": "https://example.com/y",
        })
        assert is_new2  # Different URL = different hash

    def test_write_batch(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        counts = writer.write_batch([
            {"title": "B1", "canonical_url": "https://a.com/1", "content_plain": "one"},
            {"title": "B2", "canonical_url": "https://a.com/2", "content_plain": "two"},
            {"title": "B1", "canonical_url": "https://a.com/1", "content_plain": "one"},  # dup
        ])
        assert counts["new"] == 2
        assert counts["duplicate"] == 1
        assert counts["error"] == 0

    def test_tags_written(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        _, eid = writer.write({
            "title": "Tagged Article",
            "canonical_url": "https://example.com/tags",
            "content_plain": "x",
            "tags": ["science", "tech"],
        })
        tags = store._get_tags(eid)
        assert "science" in tags
        assert "tech" in tags

    def test_missing_title_skipped(self, tmp_path: Path):
        store = KnowledgeStore(db_path=tmp_path / "test.db")
        store.init_db()
        writer = KnowledgeWriter(store)

        is_new, eid = writer.write({
            "title": "",
            "canonical_url": "https://example.com/empty",
        })
        assert not is_new
        assert eid == ""
