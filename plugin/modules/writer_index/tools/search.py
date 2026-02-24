"""Full-text search tools: search_fulltext, get_index_stats."""

from plugin.framework.tool_base import ToolBase


class SearchFulltext(ToolBase):
    name = "search_fulltext"
    description = (
        "Full-text search with Snowball stemming. Supports boolean queries: "
        "AND (default), OR, NOT, NEAR/N. "
        "Language auto-detected from document locale. "
        "Returns matching paragraphs with context and nearest heading bookmark."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query. Examples: 'climate change', "
                    "'energy AND renewable', 'solar OR wind', "
                    "'climate NOT politics', 'ocean NEAR/3 warming'"
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 20)",
            },
            "context_paragraphs": {
                "type": "integer",
                "description": "Paragraphs of context around each match (default: 1)",
            },
        },
        "required": ["query"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        idx_svc = ctx.services.writer_index
        try:
            result = idx_svc.search_boolean(
                ctx.doc,
                kwargs["query"],
                max_results=kwargs.get("max_results", 20),
                context_paragraphs=kwargs.get("context_paragraphs", 1),
            )
            return {"status": "ok", **result}
        except ValueError as e:
            return {"status": "error", "error": str(e)}


class GetIndexStats(ToolBase):
    name = "get_index_stats"
    description = (
        "Get search index statistics: paragraph count, unique stems, "
        "language, build time, and top 20 most frequent stems."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        idx_svc = ctx.services.writer_index
        result = idx_svc.get_index_stats(ctx.doc)
        return {"status": "ok", **result}
