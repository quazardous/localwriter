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


class ResolveComment(ToolBase):
    """Resolve a comment with an optional reason."""

    name = "resolve_comment"
    description = (
        "Resolve a comment with an optional reason. Adds a reply "
        "with the resolution text, then marks as resolved."
    )
    parameters = {
        "type": "object",
        "properties": {
            "comment_name": {
                "type": "string",
                "description": "The 'name' field returned by list_comments.",
            },
            "resolution": {
                "type": "string",
                "description": "Optional resolution text added as a reply.",
            },
            "author": {
                "type": "string",
                "description": "Author name for the resolution reply. Default: AI.",
            },
        },
        "required": ["comment_name"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        comment_name = kwargs.get("comment_name", "")
        resolution = kwargs.get("resolution", "")
        author = kwargs.get("author", "AI")

        if not comment_name:
            return {"status": "error", "message": "comment_name is required."}

        doc = ctx.doc
        doc_text = doc.getText()
        fields = doc.getTextFields()
        enum = fields.createEnumeration()

        target = None
        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue
            try:
                name = field.getPropertyValue("Name")
            except Exception:
                continue
            if name == comment_name:
                target = field
                break

        if target is None:
            return {
                "status": "not_found",
                "message": "Comment '%s' not found." % comment_name,
            }

        if resolution:
            reply = doc.createInstance(
                "com.sun.star.text.textfield.Annotation"
            )
            reply.setPropertyValue("ParentName", comment_name)
            reply.setPropertyValue("Content", resolution)
            reply.setPropertyValue("Author", author)
            anchor = target.getAnchor()
            cursor = doc_text.createTextCursorByRange(anchor.getStart())
            doc_text.insertTextContent(cursor, reply, False)

        target.setPropertyValue("Resolved", True)

        return {
            "status": "ok",
            "comment_name": comment_name,
            "resolved": True,
        }


class ScanTasks(ToolBase):
    """Scan comments for actionable task prefixes."""

    name = "scan_tasks"
    description = (
        "Scan comments for actionable task prefixes: TODO-AI, FIX, "
        "QUESTION, VALIDATION, NOTE. Returns unresolved tasks with locators."
    )
    parameters = {
        "type": "object",
        "properties": {
            "unresolved_only": {
                "type": "boolean",
                "description": "Only return unresolved tasks. Default: true.",
            },
            "prefix_filter": {
                "type": "string",
                "description": "Filter by a specific task prefix.",
                "enum": ["TODO-AI", "FIX", "QUESTION", "VALIDATION", "NOTE"],
            },
        },
        "required": [],
    }
    doc_types = ["writer"]

    _TASK_PREFIXES = ("TODO-AI", "FIX", "QUESTION", "VALIDATION", "NOTE")

    def execute(self, ctx, **kwargs):
        unresolved_only = kwargs.get("unresolved_only", True)
        prefix_filter = kwargs.get("prefix_filter", None)

        doc = ctx.doc
        doc_svc = ctx.services.document
        para_ranges = doc_svc.get_paragraph_ranges(doc)
        text_obj = doc.getText()

        fields = doc.getTextFields()
        enum = fields.createEnumeration()
        tasks = []

        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue

            try:
                content = field.getPropertyValue("Content")
            except Exception:
                continue

            matched_prefix = None
            for prefix in self._TASK_PREFIXES:
                if content.startswith(prefix):
                    matched_prefix = prefix
                    break
            if matched_prefix is None:
                continue

            if prefix_filter and matched_prefix != prefix_filter:
                continue

            if unresolved_only:
                try:
                    resolved = field.getPropertyValue("Resolved")
                except Exception:
                    resolved = False
                if resolved:
                    continue

            entry = _read_annotation(field, para_ranges, text_obj)
            entry["prefix"] = matched_prefix
            tasks.append(entry)

        return {"status": "ok", "tasks": tasks, "count": len(tasks)}


class GetWorkflowStatus(ToolBase):
    """Read the master workflow dashboard comment."""

    name = "get_workflow_status"
    description = (
        "Read the master workflow dashboard comment "
        "(author: MCP-WORKFLOW). Returns key-value pairs."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        fields = doc.getTextFields()
        enum = fields.createEnumeration()

        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue
            try:
                author = field.getPropertyValue("Author")
            except Exception:
                continue
            if author != "MCP-WORKFLOW":
                continue

            try:
                content = field.getPropertyValue("Content")
            except Exception:
                content = ""

            workflow = {}
            for line in content.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    workflow[key.strip()] = value.strip()

            return {"status": "ok", "workflow": workflow}

        return {"status": "ok", "workflow": None}


class SetWorkflowStatus(ToolBase):
    """Create or update the master workflow dashboard comment."""

    name = "set_workflow_status"
    description = (
        "Create or update the master workflow dashboard comment. "
        "Content should be key: value lines."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Workflow status as key: value lines.",
            },
        },
        "required": ["content"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        content = kwargs.get("content", "")
        if not content:
            return {"status": "error", "message": "content is required."}

        doc = ctx.doc
        doc_text = doc.getText()
        fields = doc.getTextFields()
        enum = fields.createEnumeration()

        existing = None
        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue
            try:
                author = field.getPropertyValue("Author")
            except Exception:
                continue
            if author == "MCP-WORKFLOW":
                existing = field
                break

        if existing is not None:
            existing.setPropertyValue("Content", content)
        else:
            annotation = doc.createInstance(
                "com.sun.star.text.textfield.Annotation"
            )
            annotation.setPropertyValue("Author", "MCP-WORKFLOW")
            annotation.setPropertyValue("Content", content)
            cursor = doc_text.createTextCursor()
            cursor.gotoStart(False)
            doc_text.insertTextContent(cursor, annotation, False)

        return {"status": "ok", "message": "Workflow status updated."}


class CheckStopConditions(ToolBase):
    """Check for stop/cancel signals in comments."""

    name = "check_stop_conditions"
    description = (
        "Check for stop signals: unresolved comments starting with "
        "STOP or CANCEL, or workflow status containing 'stop' or 'pause'. "
        "Use between batch operations to respect human intervention."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        fields = doc.getTextFields()
        enum = fields.createEnumeration()

        stop_signals = []
        workflow_stop = False

        while enum.hasMoreElements():
            field = enum.nextElement()
            if not field.supportsService(
                "com.sun.star.text.textfield.Annotation"
            ):
                continue

            try:
                content = field.getPropertyValue("Content")
                author = field.getPropertyValue("Author")
                resolved = field.getPropertyValue("Resolved")
            except Exception:
                continue

            # Check workflow dashboard for stop/pause
            if author == "MCP-WORKFLOW" and content:
                lower = content.lower()
                if "stop" in lower or "pause" in lower:
                    workflow_stop = True

            # Check for STOP/CANCEL comments
            if not resolved and content:
                upper = content.strip().upper()
                if upper.startswith("STOP") or upper.startswith("CANCEL"):
                    stop_signals.append({
                        "author": author,
                        "content": content[:100],
                    })

        should_stop = bool(stop_signals) or workflow_stop
        return {
            "status": "ok",
            "should_stop": should_stop,
            "workflow_stop": workflow_stop,
            "stop_signals": stop_signals,
            "count": len(stop_signals),
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
