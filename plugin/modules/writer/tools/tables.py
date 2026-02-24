"""Writer table tools."""

import logging

from plugin.framework.tool_base import ToolBase

log = logging.getLogger("localwriter.writer")


class ListTables(ToolBase):
    """List all text tables in the document."""

    name = "list_tables"
    description = (
        "List all text tables in the document with their names "
        "and dimensions (rows x cols)."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        doc = ctx.doc
        if not hasattr(doc, "getTextTables"):
            return {"status": "error", "message": "Document does not support text tables."}

        tables_sup = doc.getTextTables()
        tables = []
        for name in tables_sup.getElementNames():
            table = tables_sup.getByName(name)
            tables.append({
                "name": name,
                "rows": table.getRows().getCount(),
                "cols": table.getColumns().getCount(),
            })
        return {"status": "ok", "tables": tables, "count": len(tables)}


class ReadTable(ToolBase):
    """Read all cell contents from a named Writer table."""

    name = "read_table"
    description = "Read all cell contents from a named Writer table as a 2D array."
    parameters = {
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "The table name from list_tables.",
            },
        },
        "required": ["table_name"],
    }
    doc_types = ["writer"]

    def execute(self, ctx, **kwargs):
        table_name = kwargs.get("table_name", "")
        if not table_name:
            return {"status": "error", "message": "table_name is required."}

        doc = ctx.doc
        tables_sup = doc.getTextTables()
        if not tables_sup.hasByName(table_name):
            available = list(tables_sup.getElementNames())
            return {
                "status": "error",
                "message": "Table '%s' not found." % table_name,
                "available": available,
            }

        table = tables_sup.getByName(table_name)
        rows = table.getRows().getCount()
        cols = table.getColumns().getCount()
        data = []
        for r in range(rows):
            row_data = []
            for c in range(cols):
                col_letter = _col_letter(c)
                cell_ref = "%s%d" % (col_letter, r + 1)
                try:
                    row_data.append(table.getCellByName(cell_ref).getString())
                except Exception:
                    row_data.append("")
            data.append(row_data)

        return {
            "status": "ok",
            "table_name": table_name,
            "rows": rows,
            "cols": cols,
            "data": data,
        }


class WriteTableCell(ToolBase):
    """Write a value to a specific cell in a Writer table."""

    name = "write_table_cell"
    description = (
        "Write a value to a specific cell in a named Writer table. "
        "Use Excel-style cell references (e.g. 'A1', 'B2'). "
        "Numeric strings are stored as numbers automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "table_name": {
                "type": "string",
                "description": "The table name from list_tables.",
            },
            "cell": {
                "type": "string",
                "description": "Cell reference, e.g. 'A1', 'B3'.",
            },
            "value": {
                "type": "string",
                "description": "The value to write.",
            },
        },
        "required": ["table_name", "cell", "value"],
    }
    doc_types = ["writer"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        table_name = kwargs.get("table_name", "")
        cell_ref = kwargs.get("cell", "")
        value = kwargs.get("value", "")

        if not table_name or not cell_ref:
            return {"status": "error", "message": "table_name and cell are required."}

        doc = ctx.doc
        tables_sup = doc.getTextTables()
        if not tables_sup.hasByName(table_name):
            return {"status": "error", "message": "Table '%s' not found." % table_name}

        table = tables_sup.getByName(table_name)
        cell_obj = table.getCellByName(cell_ref)
        if cell_obj is None:
            return {
                "status": "error",
                "message": "Cell '%s' not found in table '%s'." % (cell_ref, table_name),
            }

        try:
            cell_obj.setValue(float(value))
        except (ValueError, TypeError):
            cell_obj.setString(str(value))

        return {
            "status": "ok",
            "table": table_name,
            "cell": cell_ref,
            "value": value,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _col_letter(c):
    """Convert 0-based column index to Excel-style letter(s)."""
    if c < 26:
        return chr(ord("A") + c)
    return "A" + chr(ord("A") + c - 26)
