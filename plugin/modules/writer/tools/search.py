"""Writer search tools: search_in_document, replace_in_document."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class SearchInDocument(ToolBase):
    """Search for text in a document with paragraph context."""

    name = "search_in_document"
    description = (
        "Search for text in the document using LibreOffice native search. "
        "Returns matches with surrounding paragraph text for context."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search string or regex pattern.",
            },
            "regex": {
                "type": "boolean",
                "description": "Use regular expression (default: false).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search (default: false).",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default: 20).",
            },
            "context_paragraphs": {
                "type": "integer",
                "description": (
                    "Number of paragraphs of context around each match "
                    "(default: 1)."
                ),
            },
        },
        "required": ["pattern"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        pattern = kwargs.get("pattern", "")
        if not pattern:
            return {"status": "error", "message": "pattern is required."}

        regex = kwargs.get("regex", False)
        case_sensitive = kwargs.get("case_sensitive", False)
        max_results = kwargs.get("max_results", 20)
        context_paragraphs = kwargs.get("context_paragraphs", 1)

        doc = ctx.doc
        doc_svc = ctx.services.document

        try:
            search_desc = doc.createSearchDescriptor()
            search_desc.SearchString = pattern
            search_desc.SearchRegularExpression = bool(regex)
            search_desc.SearchCaseSensitive = bool(case_sensitive)

            found = doc.findAll(search_desc)
            if found is None or found.getCount() == 0:
                return {"status": "ok", "matches": [], "count": 0}

            total_found = found.getCount()
            text_obj = doc.getText()
            para_ranges = doc_svc.get_paragraph_ranges(doc)
            para_count = len(para_ranges)

            # Determine which matches to process and which paragraphs
            # we need text from (for context).
            limit = min(total_found, max_results)
            match_indices = []
            needed_paras = set()

            for i in range(limit):
                match_range = found.getByIndex(i)
                idx = doc_svc.find_paragraph_for_range(
                    match_range, para_ranges, text_obj
                )
                match_indices.append((i, match_range, idx))
                ctx_lo = max(0, idx - context_paragraphs)
                ctx_hi = min(para_count, idx + context_paragraphs + 1)
                for j in range(ctx_lo, ctx_hi):
                    needed_paras.add(j)

            # Read only the paragraphs we need
            para_texts = {}
            if needed_paras:
                text_enum = text_obj.createEnumeration()
                pidx = 0
                max_needed = max(needed_paras)
                while text_enum.hasMoreElements():
                    el = text_enum.nextElement()
                    if pidx in needed_paras:
                        if el.supportsService(
                            "com.sun.star.text.Paragraph"
                        ):
                            para_texts[pidx] = el.getString()
                        else:
                            para_texts[pidx] = "[Table]"
                    pidx += 1
                    if pidx > max_needed:
                        break

            # Build result list
            results = []
            for i, match_range, match_para_idx in match_indices:
                match_text = match_range.getString()
                ctx_start = max(0, match_para_idx - context_paragraphs)
                ctx_end = min(
                    para_count, match_para_idx + context_paragraphs + 1
                )
                context = [
                    {"index": j, "text": para_texts.get(j, "")}
                    for j in range(ctx_start, ctx_end)
                ]
                results.append({
                    "text": match_text,
                    "paragraph_index": match_para_idx,
                    "context": context,
                })

            return {
                "status": "ok",
                "matches": results,
                "count": total_found,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


class ReplaceInDocument(ToolBase):
    """Find and replace text preserving formatting."""

    name = "replace_in_document"
    description = (
        "Find and replace text in the document with regex support. "
        "Preserves existing formatting. Returns count of replacements."
    )
    parameters = {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Text or regex pattern to find.",
            },
            "replace": {
                "type": "string",
                "description": "Replacement text.",
            },
            "regex": {
                "type": "boolean",
                "description": "Use regular expression (default: false).",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive matching (default: false).",
            },
            "replace_all": {
                "type": "boolean",
                "description": (
                    "Replace all occurrences (default: true). "
                    "Set to false to replace only the first match."
                ),
            },
        },
        "required": ["search", "replace"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        search = kwargs.get("search", "")
        replace = kwargs.get("replace", "")
        if not search:
            return {"status": "error", "message": "search is required."}

        regex = kwargs.get("regex", False)
        case_sensitive = kwargs.get("case_sensitive", False)
        replace_all = kwargs.get("replace_all", True)

        doc = ctx.doc

        try:
            replace_desc = doc.createReplaceDescriptor()
            replace_desc.SearchString = search
            replace_desc.ReplaceString = replace
            replace_desc.SearchRegularExpression = bool(regex)
            replace_desc.SearchCaseSensitive = bool(case_sensitive)

            if replace_all:
                count = doc.replaceAll(replace_desc)
            else:
                # Replace only the first match
                found = doc.findFirst(replace_desc)
                if found is not None:
                    found.setString(replace)
                    count = 1
                else:
                    count = 0

            # Invalidate document cache after edits
            if count > 0:
                doc_svc = ctx.services.document
                doc_svc.invalidate_cache(doc)

            return {
                "status": "ok",
                "replacements": count,
                "search": search,
                "replace": replace,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
