"""Structural tools: list_sections, goto_page, get_page_objects, refresh_indexes."""

from plugin.framework.tool_base import ToolBase


class ListSections(ToolBase):
    name = "list_sections"
    description = "List all named sections in the document."
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getTextSections"):
            return {"status": "ok", "sections": [], "count": 0}
        try:
            supplier = doc.getTextSections()
            names = supplier.getElementNames()
            sections = []
            for name in names:
                section = supplier.getByName(name)
                sections.append({
                    "name": name,
                    "is_visible": getattr(section, "IsVisible", True),
                    "is_protected": getattr(section, "IsProtected", False),
                })
            return {"status": "ok", "sections": sections, "count": len(sections)}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class GotoPage(ToolBase):
    name = "goto_page"
    description = "Navigate the view cursor to a specific page."
    parameters = {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "Page number to navigate to"},
        },
        "required": ["page"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        try:
            controller = ctx.doc.getCurrentController()
            vc = controller.getViewCursor()
            vc.jumpToPage(kwargs["page"])
            return {"status": "ok", "page": vc.getPage()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class GetPageObjects(ToolBase):
    name = "get_page_objects"
    description = (
        "Get images, tables, and frames on a specific page. "
        "Provide page number, locator, or paragraph_index."
    )
    parameters = {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "Page number"},
            "locator": {"type": "string", "description": "Locator to determine page"},
            "paragraph_index": {"type": "integer", "description": "Paragraph index to determine page"},
        },
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        doc_svc = ctx.services.document
        page = kwargs.get("page")

        if page is None:
            locator = kwargs.get("locator")
            para_idx = kwargs.get("paragraph_index")
            if locator:
                try:
                    resolved = doc_svc.resolve_locator(doc, locator)
                    para_idx = resolved.get("para_index", 0)
                except ValueError as e:
                    return {"status": "error", "error": str(e)}
            if para_idx is not None:
                page = doc_svc.get_page_for_paragraph(doc, para_idx)
            else:
                try:
                    page = doc.getCurrentController().getViewCursor().getPage()
                except Exception:
                    page = 1

        try:
            controller = doc.getCurrentController()
            vc = controller.getViewCursor()
            saved = doc.getText().createTextCursorByRange(vc.getStart())
            doc.lockControllers()
            try:
                objects = self._scan_page(doc, vc, page)
            finally:
                vc.gotoRange(saved, False)
                doc.unlockControllers()
            return {"status": "ok", "page": page, **objects}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _scan_page(self, doc, vc, page):
        images = []
        if hasattr(doc, "getGraphicObjects"):
            for name in doc.getGraphicObjects().getElementNames():
                try:
                    g = doc.getGraphicObjects().getByName(name)
                    vc.gotoRange(g.getAnchor(), False)
                    if vc.getPage() == page:
                        size = g.getPropertyValue("Size")
                        images.append({
                            "name": name,
                            "width_mm": size.Width // 100,
                            "height_mm": size.Height // 100,
                            "title": g.getPropertyValue("Title"),
                        })
                except Exception:
                    pass

        tables = []
        if hasattr(doc, "getTextTables"):
            for name in doc.getTextTables().getElementNames():
                try:
                    t = doc.getTextTables().getByName(name)
                    vc.gotoRange(t.getAnchor(), False)
                    if vc.getPage() == page:
                        tables.append({
                            "name": name,
                            "rows": t.getRows().getCount(),
                            "cols": t.getColumns().getCount(),
                        })
                except Exception:
                    pass

        frames = []
        if hasattr(doc, "getTextFrames"):
            for fname in doc.getTextFrames().getElementNames():
                try:
                    fr = doc.getTextFrames().getByName(fname)
                    vc.gotoRange(fr.getAnchor(), False)
                    if vc.getPage() == page:
                        size = fr.getPropertyValue("Size")
                        frames.append({
                            "name": fname,
                            "width_mm": size.Width // 100,
                            "height_mm": size.Height // 100,
                        })
                except Exception:
                    pass

        return {"images": images, "tables": tables, "frames": frames}


class RefreshIndexes(ToolBase):
    name = "refresh_indexes"
    description = "Refresh all document indexes (TOC, bibliography, etc.)."
    parameters = {"type": "object", "properties": {}, "required": []}
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getDocumentIndexes"):
            return {"status": "error", "error": "Document does not support indexes"}
        try:
            indexes = doc.getDocumentIndexes()
            count = indexes.getCount()
            refreshed = []
            for i in range(count):
                idx = indexes.getByIndex(i)
                idx.update()
                name = idx.getName() if hasattr(idx, "getName") else "index_%d" % i
                refreshed.append(name)
            return {"status": "ok", "refreshed": refreshed, "count": count}
        except Exception as e:
            return {"status": "error", "error": str(e)}
