"""Generic document information tool."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.common")


class GetDocumentInfo(ToolBase):
    """Return generic metadata about the current document."""

    name = "get_document_info"
    description = (
        "Returns generic document metadata: title, file path, document type, "
        "modification status, and document properties (author, subject, etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = None  # works with all document types

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        url = doc.getURL()

        # Basic info.
        info = {
            "status": "ok",
            "doc_type": ctx.doc_type,
            "file_url": url or None,
            "is_modified": doc.isModified(),
            "is_new": not bool(url),
        }

        # Title: prefer document properties, fall back to URL filename.
        try:
            props = doc.getDocumentProperties()
            title = props.Title
            if not title and url:
                # Extract filename from file:///path/to/doc.odt
                title = url.rsplit("/", 1)[-1]
            info["title"] = title or "(untitled)"
            info["author"] = props.Author or None
            info["subject"] = props.Subject or None
            info["description"] = props.Description or None
        except Exception:
            if url:
                info["title"] = url.rsplit("/", 1)[-1]
            else:
                info["title"] = "(untitled)"

        return info
