"""Writer content tools — read, apply, find, and paragraph operations."""

import logging

from plugin.framework.tool_base import ToolBase
from plugin.modules.writer import format_support

log = logging.getLogger("localwriter.writer")


# ------------------------------------------------------------------
# GetDocumentContent
# ------------------------------------------------------------------

class GetDocumentContent(ToolBase):
    """Export the document (or a portion) as formatted content."""

    name = "get_document_content"
    description = (
        "Get document (or selection/range) content. "
        "Result includes document_length. "
        "scope: full, selection, or range (requires start, end)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["full", "selection", "range"],
                "description": (
                    "Return full document (default), current "
                    "selection/cursor region, or a character range "
                    "(requires start and end)."
                ),
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return.",
            },
            "start": {
                "type": "integer",
                "description": "Start character offset (0-based). Required for scope 'range'.",
            },
            "end": {
                "type": "integer",
                "description": "End character offset (exclusive). Required for scope 'range'.",
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        scope = kwargs.get("scope", "full")
        max_chars = kwargs.get("max_chars")
        range_start = kwargs.get("start") if scope == "range" else None
        range_end = kwargs.get("end") if scope == "range" else None

        if scope == "range" and (range_start is None or range_end is None):
            return {"status": "error", "message": "scope 'range' requires start and end."}

        content = format_support.document_to_content(
            ctx.doc, ctx.ctx, ctx.services,
            max_chars=max_chars, scope=scope,
            range_start=range_start, range_end=range_end,
        )
        doc_len = ctx.services.document.get_document_length(ctx.doc)
        result = {
            "status": "ok",
            "content": content,
            "length": len(content),
            "document_length": doc_len,
        }
        if scope == "range" and range_start is not None:
            result["start"] = int(range_start)
            result["end"] = int(range_end)
        return result


# ------------------------------------------------------------------
# ApplyDocumentContent
# ------------------------------------------------------------------

class ApplyDocumentContent(ToolBase):
    """Insert or replace content in the document."""

    name = "apply_document_content"
    description = (
        "Insert or replace content. Preferred for partial edits: "
        "target='search' with search= and content=. "
        "For whole doc: target='full'. "
        "Use target='range' with start/end."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The new content (Markdown or HTML).",
            },
            "target": {
                "type": "string",
                "enum": ["beginning", "end", "selection", "search", "full", "range"],
                "description": (
                    "Where to apply: full, range (start+end), "
                    "search (needs search), beginning, end, selection."
                ),
            },
            "start": {
                "type": "integer",
                "description": "Start character offset. Required for target 'range'.",
            },
            "end": {
                "type": "integer",
                "description": "End character offset. Required for target 'range'.",
            },
            "search": {
                "type": "string",
                "description": "Text to find. Required for target 'search'.",
            },
            "all_matches": {
                "type": "boolean",
                "description": "Replace all occurrences (true) or first only. Default false.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search. Default true.",
            },
        },
        "required": ["content", "target"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        content = kwargs.get("content", "")
        target = kwargs.get("target")

        # Normalize list input.
        if isinstance(content, list):
            content = "\n".join(str(x) for x in content)
        if isinstance(content, str):
            content = content.replace("\\n", "\n").replace("\\t", "\t")

        if not target:
            return {"status": "error", "message": "target is required."}

        # Detect markup BEFORE any HTML wrapping.
        raw_content = content
        use_preserve = isinstance(content, str) and not format_support.content_has_markup(content)

        config_svc = ctx.services.get("config")

        # -- search -------------------------------------------------
        if target == "search":
            search = kwargs.get("search")
            if not search and search != "":
                return {"status": "error", "message": "search is required when target is 'search'."}
            all_matches = kwargs.get("all_matches", False)
            case_sensitive = kwargs.get("case_sensitive", True)
            try:
                if use_preserve:
                    count = _preserving_search_replace(
                        ctx.doc, ctx.ctx, raw_content, search,
                        all_matches=all_matches,
                        case_sensitive=case_sensitive,
                    )
                else:
                    count = format_support.apply_content_at_search(
                        ctx.doc, ctx.ctx, content, search,
                        all_matches=all_matches,
                        case_sensitive=case_sensitive,
                        config_svc=config_svc,
                    )
                msg = "Replaced %d occurrence(s)." % count
                if use_preserve and count > 0:
                    msg += " (formatting preserved)"
                if count == 0:
                    msg += (
                        " No matches found. Try find_text first, then "
                        "use target='range'."
                    )
                return {"status": "ok", "message": msg}
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        # -- full ---------------------------------------------------
        if target == "full":
            try:
                if use_preserve:
                    from plugin.modules.writer.ops import get_text_cursor_at_range
                    doc_len = ctx.services.document.get_document_length(ctx.doc)
                    rng = get_text_cursor_at_range(ctx.doc, 0, doc_len)
                    format_support.replace_preserving_format(
                        ctx.doc, rng, raw_content, ctx.ctx
                    )
                    return {"status": "ok", "message": "Replaced entire document. (formatting preserved)"}
                else:
                    format_support.replace_full_document(
                        ctx.doc, ctx.ctx, content, config_svc=config_svc
                    )
                    return {"status": "ok", "message": "Replaced entire document."}
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        # -- range --------------------------------------------------
        if target == "range":
            start_val = kwargs.get("start")
            end_val = kwargs.get("end")
            if start_val is None or end_val is None:
                return {"status": "error", "message": "target 'range' requires start and end."}
            try:
                if use_preserve:
                    from plugin.modules.writer.ops import get_text_cursor_at_range
                    rng = get_text_cursor_at_range(
                        ctx.doc, int(start_val), int(end_val)
                    )
                    format_support.replace_preserving_format(
                        ctx.doc, rng, raw_content, ctx.ctx
                    )
                    return {
                        "status": "ok",
                        "message": "Replaced range [%s, %s). (formatting preserved)"
                        % (start_val, end_val),
                    }
                else:
                    format_support.apply_content_at_range(
                        ctx.doc, ctx.ctx, content,
                        int(start_val), int(end_val),
                        config_svc=config_svc,
                    )
                    return {
                        "status": "ok",
                        "message": "Replaced range [%s, %s)." % (start_val, end_val),
                    }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        # -- beginning / end / selection ----------------------------
        if target in ("beginning", "end", "selection"):
            try:
                format_support.insert_content_at_position(
                    ctx.doc, ctx.ctx, content, target,
                    config_svc=config_svc,
                )
                return {
                    "status": "ok",
                    "message": "Inserted content at %s." % target,
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        return {"status": "error", "message": "Unknown target: %s" % target}


# ------------------------------------------------------------------
# FindText
# ------------------------------------------------------------------

class FindText(ToolBase):
    """Find text in the document."""

    name = "find_text"
    description = (
        "Finds text in the document. Returns {start, end, text} per match. "
        "Use with apply_document_content (search= or target=range)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Text to search for.",
            },
            "start": {
                "type": "integer",
                "description": "Start offset to search from (default 0).",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum matches to return.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search. Default true.",
            },
        },
        "required": ["search"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        search = kwargs.get("search")
        if not search:
            return {"status": "error", "message": "search parameter is required."}
        start = kwargs.get("start", 0)
        limit = kwargs.get("limit")
        case_sensitive = kwargs.get("case_sensitive", True)

        ranges = format_support.find_text_ranges(
            ctx.doc, ctx.ctx, search,
            start=start, limit=limit, case_sensitive=case_sensitive,
        )
        return {"status": "ok", "ranges": ranges}


# ------------------------------------------------------------------
# ReadParagraphs
# ------------------------------------------------------------------

class ReadParagraphs(ToolBase):
    """Read a range of paragraphs by index."""

    name = "read_paragraphs"
    description = (
        "Read a range of paragraphs by index. "
        "Useful for scanning text between headings."
    )
    parameters = {
        "type": "object",
        "properties": {
            "start_index": {
                "type": "integer",
                "description": "Starting paragraph index (0-based).",
            },
            "count": {
                "type": "integer",
                "description": "Number of paragraphs to read (default 10).",
            },
        },
        "required": ["start_index"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        start = kwargs.get("start_index", 0)
        count = kwargs.get("count", 10)
        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(ctx.doc)
        end = min(start + count, len(para_ranges))

        paragraphs = []
        for i in range(start, end):
            p = para_ranges[i]
            text = p.getString() if hasattr(p, "getString") else "[Object]"
            paragraphs.append({"index": i, "text": text})

        return {
            "status": "ok",
            "paragraphs": paragraphs,
            "total": len(para_ranges),
        }


# ------------------------------------------------------------------
# InsertAtParagraph
# ------------------------------------------------------------------

class InsertAtParagraph(ToolBase):
    """Insert text at a specific paragraph index."""

    name = "insert_at_paragraph"
    description = "Insert text at a specific paragraph index."
    parameters = {
        "type": "object",
        "properties": {
            "paragraph_index": {
                "type": "integer",
                "description": "0-based paragraph index.",
            },
            "text": {
                "type": "string",
                "description": "Text to insert.",
            },
            "position": {
                "type": "string",
                "enum": ["before", "after", "replace"],
                "description": "Position relative to the target paragraph (default: 'before').",
            },
        },
        "required": ["paragraph_index", "text"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        para_index = kwargs.get("paragraph_index")
        text_to_insert = kwargs.get("text", "")
        position = kwargs.get("position", "before")

        if para_index is None:
            return {"status": "error", "message": "paragraph_index is required."}

        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(ctx.doc)

        if para_index < 0 or para_index >= len(para_ranges):
            return {
                "status": "error",
                "message": "Paragraph index %d out of range (0..%d)."
                % (para_index, len(para_ranges) - 1),
            }

        target_para = para_ranges[para_index]
        text = ctx.doc.getText()
        cursor = text.createTextCursorByRange(target_para.getStart())

        if position == "after":
            cursor.gotoRange(target_para.getEnd(), False)
            text.insertString(cursor, "\n" + text_to_insert, False)
        elif position == "replace":
            cursor.gotoRange(target_para.getEnd(), True)
            cursor.setString(text_to_insert)
        else:  # before
            text.insertString(cursor, text_to_insert + "\n", False)

        return {
            "status": "ok",
            "message": "Inserted text at paragraph %d." % para_index,
        }


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _preserving_search_replace(model, uno_ctx, new_text, search_string,
                               all_matches=False, case_sensitive=True):
    """Find *search_string* and replace with *new_text* using format-preserving
    character-by-character replacement. Returns the number of replacements.
    """
    sd = model.createSearchDescriptor()
    sd.SearchString = search_string
    sd.SearchRegularExpression = False
    sd.SearchCaseSensitive = case_sensitive

    count = 0
    found = model.findFirst(sd)
    while found:
        format_support.replace_preserving_format(model, found, new_text, uno_ctx)
        count += 1
        if not all_matches:
            break
        found = model.findFirst(sd)
        if count > 200:
            break
    return count
