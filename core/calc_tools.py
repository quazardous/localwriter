"""Calc document manipulation tools for AI chat sidebar."""

import json
import logging
from core.logging import agent_log
from core.calc_bridge import CalcBridge
from core.calc_inspector import CellInspector
from core.calc_manipulator import CellManipulator
from core.calc_sheet_analyzer import SheetAnalyzer
from core.calc_error_detector import ErrorDetector

logger = logging.getLogger(__name__)

CALC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_cell_range",
            "description": "Reads values from the specified cell range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": "string",
                        "description": "Cell range (e.g. A1:D10, B2, Sheet1.A1:C5)",
                    }
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_formula",
            "description": "Writes text, number, or formula to the specified cell. Use plain text for headers (e.g. 'Total'), numbers for numeric data (e.g. '42'), and start with '=' for formulas (e.g. '=SUM(A1:A10)'). When creating a table, write all headers and data one by one if possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cell": {
                        "type": "string",
                        "description": "Target cell address (e.g. A1, B5)",
                    },
                    "formula": {
                        "type": "string",
                        "description": "Content to write: text (e.g. 'Header'), number (e.g. '100'), or formula (e.g. '=A1+B1')",
                    },
                },
                "required": ["cell", "formula"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_cell_style",
            "description": "Applies style and formatting to the specified cell or range. Typically used for visualization after writing data or merging cells.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {
                        "type": "string",
                        "description": "Target cell or range (e.g. A1, A1:D10)",
                    },
                    "bold": {"type": "boolean", "description": "Bold font"},
                    "italic": {"type": "boolean", "description": "Italic font"},
                    "font_size": {"type": "number", "description": "Font size (points)"},
                    "bg_color": {"type": "string", "description": "Background color (hex: #FF0000 or name: yellow)"},
                    "font_color": {"type": "string", "description": "Font color (hex: #000000 or name: red)"},
                    "h_align": {
                        "type": "string",
                        "enum": ["left", "center", "right", "justify"],
                        "description": "Horizontal alignment",
                    },
                    "v_align": {
                        "type": "string",
                        "enum": ["top", "center", "bottom"],
                        "description": "Vertical alignment",
                    },
                    "wrap_text": {"type": "boolean", "description": "Wrap text"},
                    "border_color": {"type": "string", "description": "Border color (hex or name). Draws a frame around the cell/range."},
                    "number_format": {"type": "string", "description": "Number format (e.g. #,##0.00, 0%, dd.mm.yyyy)"},
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sheet_summary",
            "description": "Returns a summary of the active or specified sheet (size, used cells, column headers, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Sheet name (active sheet if empty)"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_and_explain_errors",
            "description": "Detects formula errors in the specified range and provides an explanation and fix suggestion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {"type": "string", "description": "Cell range to check (e.g. A1:Z100). Full sheet if empty."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "merge_cells",
            "description": "Merges the specified cell range. Typically used for main headers. Don't forget to write text with write_formula and style with set_cell_style after merging.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {"type": "string", "description": "Range to merge (e.g. A1:D1)"},
                    "center": {"type": "boolean", "description": "Center content (default: true)"}
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sheets",
            "description": "Lists all sheet names in the workbook.",
            "parameters": {"type": "object", "properties": {}},
            "required": [],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_sheet",
            "description": "Switches to the specified sheet (makes it active).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "Name of the sheet to switch to"}
                },
                "required": ["sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_sheet",
            "description": "Creates a new sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_name": {"type": "string", "description": "New sheet name"},
                    "position": {"type": "integer", "description": "Sheet position (0-based). Appended to end if not specified."}
                },
                "required": ["sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_chart",
            "description": "Creates a chart from data. Supports bar, column, line, pie, or scatter charts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_range": {"type": "string", "description": "Range for chart data (e.g. A1:B10)"},
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "scatter", "column"],
                        "description": "Chart type",
                    },
                    "title": {"type": "string", "description": "Chart title"},
                    "position": {"type": "string", "description": "Cell where chart will be placed (e.g. E1)"},
                    "has_header": {"type": "boolean", "description": "Is first row/column a label? Default: true"}
                },
                "required": ["data_range", "chart_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sort_range",
            "description": "Sorts the specified range by a column. Use for ordering rows by values in one column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {"type": "string", "description": "Range to sort (e.g. A1:D10)"},
                    "sort_column": {"type": "integer", "description": "0-based column index within the range to sort by (default: 0)"},
                    "ascending": {"type": "boolean", "description": "True for ascending, False for descending (default: true)"},
                    "has_header": {"type": "boolean", "description": "Is the first row a header that should not be sorted? (default: true)"}
                },
                "required": ["range_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_range",
            "description": "Clears all contents (values, formulas) in the specified range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "range_name": {"type": "string", "description": "Range to clear (e.g. A1:D10)"}
                },
                "required": ["range_name"],
            },
        },
    },
]

# Shared instances for the session
_bridge = None
_inspector = None
_manipulator = None
_analyzer = None
_error_detector = None

def _get_tools(ctx):
    global _bridge, _inspector, _manipulator, _analyzer, _error_detector
    if _bridge is None:
        _bridge = CalcBridge(ctx)
        _inspector = CellInspector(_bridge)
        _manipulator = CellManipulator(_bridge)
        _analyzer = SheetAnalyzer(_bridge)
        _error_detector = ErrorDetector(_bridge, _inspector)
    return {
        "inspector": _inspector,
        "manipulator": _manipulator,
        "analyzer": _analyzer,
        "error_detector": _error_detector
    }

def _parse_color(color_str):
    if not color_str:
        return None
    color_str = color_str.strip().lower()
    color_names = {
        "red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
        "yellow": 0xFFFF00, "white": 0xFFFFFF, "black": 0x000000,
        "orange": 0xFF8C00, "purple": 0x800080, "gray": 0x808080,
    }
    if color_str in color_names:
        return color_names[color_str]
    if color_str.startswith("#"):
        try:
            return int(color_str[1:], 16)
        except ValueError:
            return None
    return None

def execute_calc_tool(tool_name, arguments, model, ctx):
    """Execute a Calc tool by name. Returns JSON result string."""
    tools = _get_tools(ctx)
    agent_log("calc_tools.py:execute_calc_tool", "Tool call", data={"tool": tool_name, "arguments": arguments})
    
    try:
        if tool_name == "read_cell_range":
            result = tools["inspector"].read_range(arguments["range_name"])
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "write_formula":
            result = tools["manipulator"].write_formula(arguments["cell"], arguments["formula"])
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "set_cell_style":
            rn = arguments["range_name"]
            tools["manipulator"].set_cell_style(
                rn,
                bold=arguments.get("bold"),
                italic=arguments.get("italic"),
                bg_color=_parse_color(arguments.get("bg_color")),
                font_color=_parse_color(arguments.get("font_color")),
                font_size=arguments.get("font_size"),
                h_align=arguments.get("h_align"),
                v_align=arguments.get("v_align"),
                wrap_text=arguments.get("wrap_text"),
                border_color=_parse_color(arguments.get("border_color"))
            )
            if arguments.get("number_format"):
                # number_format is set per cell in set_number_format, if it's a range, we'd need to loop
                # for now assume single cell or implement range loop if needed
                if ":" in rn:
                    # just apply to first for now or implement properly
                    pass
                else:
                    tools["manipulator"].set_number_format(rn, arguments["number_format"])
            return json.dumps({"status": "ok", "message": f"Style applied to {rn}"})
            
        elif tool_name == "get_sheet_summary":
            result = tools["analyzer"].get_sheet_summary(sheet_name=arguments.get("sheet_name"))
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "detect_and_explain_errors":
            result = tools["error_detector"].detect_and_explain(range_str=arguments.get("range_name"))
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "merge_cells":
            tools["manipulator"].merge_cells(arguments["range_name"], center=arguments.get("center", True))
            return json.dumps({"status": "ok", "message": f"Merged cells {arguments['range_name']}"})
            
        elif tool_name == "list_sheets":
            result = tools["manipulator"].list_sheets()
            return json.dumps({"status": "ok", "result": result})
            
        elif tool_name == "switch_sheet":
            result = tools["manipulator"].switch_sheet(arguments["sheet_name"])
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "create_sheet":
            result = tools["manipulator"].create_sheet(arguments["sheet_name"], position=arguments.get("position"))
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "create_chart":
            result = tools["manipulator"].create_chart(
                arguments["data_range"],
                arguments["chart_type"],
                title=arguments.get("title"),
                position=arguments.get("position"),
                has_header=arguments.get("has_header", True)
            )
            return json.dumps({"status": "ok", "message": result})
            
        elif tool_name == "sort_range":
            result = tools["manipulator"].sort_range(
                arguments["range_name"],
                sort_column=arguments.get("sort_column", 0),
                ascending=arguments.get("ascending", True),
                has_header=arguments.get("has_header", True)
            )
            return json.dumps({"status": "ok", "message": result})

        elif tool_name == "clear_range":
            tools["manipulator"].clear_range(arguments["range_name"])
            return json.dumps({"status": "ok", "message": f"Cleared range {arguments['range_name']}"})
            
        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {tool_name}"})
            
    except Exception as e:
        logger.exception("Error executing Calc tool %s", tool_name)
        return json.dumps({"status": "error", "message": str(e)})
