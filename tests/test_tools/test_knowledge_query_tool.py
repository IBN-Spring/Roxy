"""Tests for KnowledgeQueryTool — search KB from within agent chat."""

from pathlib import Path

import pytest

from roxy.tools.base import ToolContext
from roxy.tools.builtin.knowledge_query import KnowledgeQueryTool


class TestKnowledgeQueryTool:
    def test_risk_level(self):
        from roxy.tools.base import RiskLevel
        tool = KnowledgeQueryTool()
        assert tool.risk_level == RiskLevel.safe

    def test_schema_has_query_required(self):
        tool = KnowledgeQueryTool()
        schema = tool.to_openai_schema()
        required = schema["function"]["parameters"].get("required", [])
        assert "query" in required

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, tmp_path: Path):
        tool = KnowledgeQueryTool()
        ctx = ToolContext(workspace_root=tmp_path)
        result = await tool.execute({"query": ""}, ctx)
        assert not result.success

    @pytest.mark.asyncio
    async def test_search_empty_kb(self, tmp_path: Path):
        """Searching an empty KB returns a friendly message."""
        tool = KnowledgeQueryTool()
        ctx = ToolContext(workspace_root=tmp_path)

        # Redirect KB to tmp_path
        import roxy.knowledge.store as ks
        original = ks.knowledge_db
        test_db = tmp_path / "roxy.db"
        ks.knowledge_db = lambda: test_db

        try:
            result = await tool.execute({"query": "nonexistent"}, ctx)
            assert result.success
            assert "No results" in result.content
        finally:
            ks.knowledge_db = original

    @pytest.mark.asyncio
    async def test_search_finds_inserted_entry(self, tmp_path: Path):
        """Insert an entry into the KB, then the tool finds it."""
        from roxy.knowledge.schema import KnowledgeEntry
        from roxy.knowledge.store import KnowledgeStore

        test_db = tmp_path / "roxy.db"
        store = KnowledgeStore(db_path=test_db)
        store.init_db()
        store.insert_entry(KnowledgeEntry(
            title="Test KB Entry",
            canonical_url="https://example.com/kb-test",
            content_plain="Roxy knowledge base integration test.",
            collected_via="manual",
        ))

        # Redirect KB path
        import roxy.knowledge.store as ks
        original = ks.knowledge_db
        ks.knowledge_db = lambda: test_db

        tool = KnowledgeQueryTool()
        ctx = ToolContext(workspace_root=tmp_path)

        try:
            result = await tool.execute({"query": "Roxy knowledge"}, ctx)
            assert result.success
            assert "Test KB Entry" in result.content
            assert "https://example.com/kb-test" in result.content
            assert result.data["count"] >= 1
        finally:
            ks.knowledge_db = original

    @pytest.mark.asyncio
    async def test_search_with_tag_filter(self, tmp_path: Path):
        from roxy.knowledge.schema import KnowledgeEntry
        from roxy.knowledge.store import KnowledgeStore

        test_db = tmp_path / "roxy.db"
        store = KnowledgeStore(db_path=test_db)
        store.init_db()

        _, eid = store.insert_entry(KnowledgeEntry(
            title="Tagged Entry",
            canonical_url="https://example.com/tagged",
            content_plain="Entry with a specific tag.",
            collected_via="manual",
        ))
        store._add_tags(eid, ["important"])

        store.insert_entry(KnowledgeEntry(
            title="Untagged Entry",
            canonical_url="https://example.com/untagged",
            content_plain="Entry without the tag.",
            collected_via="manual",
        ))

        import roxy.knowledge.store as ks
        original = ks.knowledge_db
        ks.knowledge_db = lambda: test_db

        tool = KnowledgeQueryTool()
        ctx = ToolContext(workspace_root=tmp_path)

        try:
            result = await tool.execute({"query": "entry", "tag": "important"}, ctx)
            assert result.success
            assert "Tagged Entry" in result.content
            assert "Untagged Entry" not in result.content
        finally:
            ks.knowledge_db = original
