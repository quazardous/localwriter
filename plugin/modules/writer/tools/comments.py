"""Writer comment / annotation tools."""

import logging

from plugin.framework.tool_base import ToolBase
from plugin.modules.writer.ops import find_paragraph_for_range

log = logging.getLogger("localwriter.writer")


class ListComments(ToolBase):
    """List all comments (annotations) in the document."""

    name = "list_comments"
    description = (
        "List all comments/annotations in the document, including "
        "author, content, date, resolved status, and anchor preview."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(doc)
        text_obj = doc.getText()

        fields = doc.getTextFields()
        enum = fields.createEnumeration()
        comments = []

        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue

            entry = _read_annotation(field, para_ranges, text_obj)
            comments.append(entry)

        return {"status": "ok", "comments": comments, "count": len(comments)}


class AddComment(ToolBase):
    """Add a comment anchored to text matching *search_text*."""

    name = "add_comment"
    description = (
        "Add a comment/annotation anchored to the paragraph "
        "containing search_text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The comment text.",
            },
            "search_text": {
                "type": "string",
                "description": "Anchor the comment to text containing this string.",
            },
            "author": {
                "type": "string",
                "description": "Author name shown on the comment. Default: AI.",
            },
        },
        "required": ["content", "search_text"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        content = kwargs.get("content", "")
        search_text = kwargs.get("search_text", "")
        author = kwargs.get("author", "AI")

        if not content:
            return {"status": "error", "message": "content is required."}
        if not search_text:
            return {"status": "error", "message": "search_text is required."}

        doc = ctx.doc
        doc_text = doc.getText()

        sd = doc.createSearchDescriptor()
        sd.SearchString = search_text
        sd.SearchRegularExpression = False
        found = doc.findFirst(sd)
        if found is None:
            return {
                "status": "not_found",
                "message": "Text '%s' not found." % search_text,
            }

        annotation = doc.createInstance(
            "com.sun.star.text.textfield.Annotation"
        )
        annotation.setPropertyValue("Author", author)
        annotation.setPropertyValue("Content", content)
        cursor = doc_text.createTextCursorByRange(found.getStart())
        doc_text.insertTextContent(cursor, annotation, False)

        return {"status": "ok", "message": "Comment added.", "author": author}


class DeleteComment(ToolBase):
    """Delete a comment and its replies by comment name."""

    name = "delete_comment"
    description = (
        "Delete a comment and all its replies by the comment's "
        "name (from list_comments)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "comment_name": {
                "type": "string",
                "description": "The 'name' field returned by list_comments.",
            },
        },
        "required": ["comment_name"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        comment_name = kwargs.get("comment_name", "")
        if not comment_name:
            return {"status": "error", "message": "comment_name is required."}

        doc = ctx.doc
        text_obj = doc.getText()
        fields = doc.getTextFields()
        enum = fields.createEnumeration()

        to_delete = []
        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue
            try:
                name = field.getPropertyValue("Name")
                parent = field.getPropertyValue("ParentName")
            except Exception:
                continue
            if name == comment_name or parent == comment_name:
                to_delete.append(field)

        for field in to_delete:
            text_obj.removeTextContent(field)

        return {
            "status": "ok",
            "deleted": len(to_delete),
            "comment_name": comment_name,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _read_annotation(field, para_ranges, text_obj):
    """Extract annotation properties into a plain dict."""
    entry = {}
    for prop, default in [
        ("Author", ""),
        ("Content", ""),
        ("Name", ""),
        ("ParentName", ""),
        ("Resolved", False),
    ]:
        try:
            entry[prop.lower() if prop != "ParentName" else "parent_name"] = (
                field.getPropertyValue(prop)
            )
        except Exception:
            key = prop.lower() if prop != "ParentName" else "parent_name"
            entry[key] = default

    # Date
    try:
        dt = field.getPropertyValue("DateTimeValue")
        entry["date"] = "%04d-%02d-%02d %02d:%02d" % (
            dt.Year, dt.Month, dt.Day, dt.Hours, dt.Minutes
        )
    except Exception:
        entry["date"] = ""

    # Paragraph index and anchor preview.
    try:
        anchor = field.getAnchor()
        entry["paragraph_index"] = find_paragraph_for_range(
            anchor, para_ranges, text_obj
        )
        entry["anchor_preview"] = anchor.getString()[:80]
    except Exception:
        entry["paragraph_index"] = 0
        entry["anchor_preview"] = ""

    return entry
