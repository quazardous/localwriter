"""DocumentService — UNO document helpers and caching."""

import logging
import time

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.document")


class DocumentCache:
    """Cache for expensive UNO calls, tied to a document model."""

    _instances = {}  # {id(model): cache}

    def __init__(self):
        self.length = None
        self.para_ranges = None
        self.page_cache = {}
        self.last_invalidated = time.time()

    @classmethod
    def get(cls, model):
        mid = id(model)
        if mid not in cls._instances:
            cls._instances[mid] = DocumentCache()
        return cls._instances[mid]

    @classmethod
    def invalidate(cls, model):
        mid = id(model)
        cls._instances.pop(mid, None)

    @classmethod
    def remove(cls, model):
        """Remove cache entirely (document closed)."""
        cls._instances.pop(id(model), None)


class DocumentService(ServiceBase):
    name = "document"

    def __init__(self):
        self._ctx = None
        self._desktop = None
        self._events = None

    def initialize(self, ctx):
        self._ctx = ctx

    def set_events(self, events):
        self._events = events

    # ── Desktop / active document ─────────────────────────────────────

    def _get_desktop(self):
        if self._desktop is None and self._ctx:
            sm = self._ctx.getServiceManager()
            self._desktop = sm.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self._ctx
            )
        return self._desktop

    def get_active_document(self):
        """Return the active UNO document model, or None."""
        desktop = self._get_desktop()
        if desktop is None:
            return None
        try:
            return desktop.getCurrentComponent()
        except Exception:
            return None

    # ── Type detection ────────────────────────────────────────────────

    def is_writer(self, model):
        try:
            return model.supportsService("com.sun.star.text.TextDocument")
        except Exception:
            return False

    def is_calc(self, model):
        try:
            return model.supportsService("com.sun.star.sheet.SpreadsheetDocument")
        except Exception:
            return False

    def is_draw(self, model):
        try:
            return (
                model.supportsService("com.sun.star.drawing.DrawingDocument")
                or model.supportsService("com.sun.star.presentation.PresentationDocument")
            )
        except Exception:
            return False

    def detect_doc_type(self, model):
        """Return "writer", "calc", "draw", or None."""
        if model is None:
            return None
        if self.is_writer(model):
            return "writer"
        if self.is_calc(model):
            return "calc"
        if self.is_draw(model):
            return "draw"
        return None

    # ── Cache ─────────────────────────────────────────────────────────

    def get_cache(self, model):
        return DocumentCache.get(model)

    def invalidate_cache(self, model):
        if model is not None:
            DocumentCache.invalidate(model)

    # ── Writer helpers ────────────────────────────────────────────────

    def get_full_text(self, model, max_chars=8000):
        """Get full document text, truncated to *max_chars*."""
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            full = cursor.getString()
            if len(full) > max_chars:
                full = full[:max_chars] + "\n\n[... document truncated ...]"
            return full
        except Exception:
            return ""

    def get_document_length(self, model):
        """Return character count of the document (cached)."""
        cache = DocumentCache.get(model)
        if cache.length is not None:
            return cache.length
        try:
            text = model.getText()
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.gotoEnd(True)
            cache.length = len(cursor.getString())
            return cache.length
        except Exception:
            return 0

    def build_heading_tree(self, model):
        """Return the heading outline as a nested list of dicts.

        Each entry: {"level": int, "title": str, "children": [...]}.
        """
        try:
            text = model.getText()
            enum = text.createEnumeration()
            headings = []
            while enum.hasMoreElements():
                para = enum.nextElement()
                try:
                    level = para.getPropertyValue("OutlineLevel")
                except Exception:
                    continue
                if level > 0:
                    headings.append({
                        "level": level,
                        "title": para.getString().strip(),
                        "children": [],
                    })
            return self._nest_headings(headings)
        except Exception:
            log.exception("build_heading_tree failed")
            return []

    def _nest_headings(self, flat):
        """Convert flat list of headings into nested tree."""
        if not flat:
            return []
        root = []
        stack = []  # (level, node)
        for h in flat:
            node = {"level": h["level"], "title": h["title"], "children": []}
            while stack and stack[-1][0] >= h["level"]:
                stack.pop()
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                root.append(node)
            stack.append((h["level"], node))
        return root

    def get_paragraph_ranges(self, model):
        """Return list of paragraph UNO text range objects (cached)."""
        cache = DocumentCache.get(model)
        if cache.para_ranges is not None:
            return cache.para_ranges
        try:
            text = model.getText()
            enum = text.createEnumeration()
            ranges = []
            while enum.hasMoreElements():
                ranges.append(enum.nextElement())
            cache.para_ranges = ranges
            return ranges
        except Exception:
            return []
