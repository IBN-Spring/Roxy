"""KnowledgeQueryTool — search the Roxy knowledge base from within a chat."""

from typing import Any

from roxy.tools.base import BaseTool, RiskLevel, ToolContext, ToolResult


class KnowledgeQueryTool(BaseTool):
    """Search the user's personal knowledge base.

    Use this when the user asks about previously collected research,
    wants to find articles on a topic, or needs to recall stored information.

    Risk=safe: read-only access to local knowledge base.
    """

    name: str = "knowledge_query"
    description: str = (
        "Search the Roxy knowledge base for stored research items. "
        "Use this to find articles, papers, or notes that were previously collected "
        "via RSS, web research, or manual entry. "
        "Returns matching entries with titles, summaries, and source URLs."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for full-text search of the knowledge base.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10).",
            },
            "tag": {
                "type": "string",
                "description": "Optional: filter results to entries with this tag.",
            },
        },
        "required": ["query"],
    }
    risk_level: RiskLevel = RiskLevel.safe
    workspace_bounded: bool = False

    async def execute(self, params: dict[str, Any], ctx: ToolContext) -> ToolResult:
        query = params.get("query", "").strip()
        limit = params.get("limit", 10)

        if not query:
            return ToolResult.fail("query is required")

        try:
            from roxy.knowledge.store import KnowledgeStore
            from roxy.knowledge.query import KnowledgeQuery

            store = KnowledgeStore()
            store.init_db()

            q = KnowledgeQuery(store)

            tag = params.get("tag")
            results = q.search(query, limit=limit, tag=tag)

            if not results:
                return ToolResult.ok(
                    content=f"No results found for '{query}' in the knowledge base.",
                    data={"query": query, "count": 0},
                )

            # Format results for the model
            lines = [f"Found {len(results)} result(s) for '{query}':"]
            for i, entry in enumerate(results, 1):
                date = entry.published_at[:10] if entry.published_at else "unknown date"
                source = entry.collected_via or "unknown source"
                summary = entry.content_plain or entry.summary or "(no content)"
                if len(summary) > 300:
                    summary = summary[:300] + "..."

                lines.append(f"\n{i}. **{entry.title}**")
                lines.append(f"   URL: {entry.canonical_url}")
                lines.append(f"   Date: {date} · Source: {source}")
                if entry.tags:
                    lines.append(f"   Tags: {', '.join(entry.tags)}")
                lines.append(f"   {summary}")

            return ToolResult.ok(
                content="\n".join(lines),
                data={
                    "query": query,
                    "count": len(results),
                    "entries": [
                        {
                            "title": e.title,
                            "url": e.canonical_url,
                            "date": e.published_at,
                            "tags": e.tags,
                        }
                        for e in results
                    ],
                },
            )
        except Exception as exc:
            return ToolResult.fail(f"Knowledge base query failed: {exc}")
