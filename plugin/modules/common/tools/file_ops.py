"""File operation tools: save, export PDF."""

import logging

import uno
from com.sun.star.beans import PropertyValue

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.common")

_PDF_FILTERS = {
    "writer": "writer_pdf_Export",
    "calc": "calc_pdf_Export",
    "draw": "draw_pdf_Export",
    "impress": "impress_pdf_Export",
}


class SaveDocument(ToolBase):
    """Save the current document to its existing location."""

    name = "save_document"
    description = (
        "Saves the current document. Only works if the document has already "
        "been saved to a file (has a URL). Returns an error for unsaved "
        "new documents."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = None
    is_mutation = True

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        url = doc.getURL()
        if not url:
            return {
                "status": "error",
                "error": "Document has never been saved. Use File > Save As "
                         "in LibreOffice to save it first.",
            }

        doc.store()
        return {"status": "ok", "file_url": url}


class ExportPdf(ToolBase):
    """Export the current document as PDF."""

    name = "export_pdf"
    description = (
        "Exports the current document to a PDF file at the given path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Output PDF file path (absolute).",
            },
        },
        "required": ["path"],
    }
    doc_types = None
    is_mutation = False

    def execute(self, ctx, **kwargs):
        path = kwargs["path"]
        doc_type = ctx.doc_type

        filter_name = _PDF_FILTERS.get(doc_type)
        if not filter_name:
            return {
                "status": "error",
                "error": "Unsupported document type for PDF export: %s"
                         % doc_type,
            }

        # Convert local path to file:// URL.
        if not path.startswith("file://"):
            url = uno.systemPathToFileUrl(path)
        else:
            url = path

        pv = PropertyValue()
        pv.Name = "FilterName"
        pv.Value = filter_name

        try:
            ctx.doc.storeToURL(url, (pv,))
        except Exception as exc:
            log.exception("PDF export failed: %s", exc)
            return {"status": "error", "error": str(exc)}

        return {"status": "ok", "file_url": url, "filter": filter_name}
