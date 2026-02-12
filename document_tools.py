# document_tools.py — Writer document manipulation tools for AI chat sidebar.
# Provides JSON tool schemas (WRITER_TOOLS) and executor functions for the
# OpenAI-compatible tool-calling protocol.

import json


# ---------------------------------------------------------------------------
# Tool JSON schemas (sent to the LLM in the API request)
# ---------------------------------------------------------------------------

WRITER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "replace_text",
            "description": "Find the first occurrence of 'search' text in the document and replace it with 'replacement' text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Exact text to find in the document"},
                    "replacement": {"type": "string", "description": "Text to replace it with"}
                },
                "required": ["search", "replacement"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_replace_all",
            "description": "Replace ALL occurrences of a search string in the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Text to find (all occurrences)"},
                    "replacement": {"type": "string", "description": "Replacement text"},
                    "case_sensitive": {"type": "boolean", "description": "Whether the search is case-sensitive. Default true."}
                },
                "required": ["search", "replacement"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "insert_text",
            "description": "Insert text at a specific position in the document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to insert"},
                    "position": {
                        "type": "string",
                        "enum": ["beginning", "end", "before_selection", "after_selection"],
                        "description": "Where to insert: 'beginning' or 'end' of document, or 'before_selection'/'after_selection' relative to the current cursor selection"
                    }
                },
                "required": ["text", "position"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_selection",
            "description": "Get the text that is currently selected by the user in the document. Returns empty string if nothing is selected.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_selection",
            "description": "Replace the currently selected text with new text. Does nothing if no text is selected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_text": {"type": "string", "description": "Text to replace the current selection with"}
                },
                "required": ["new_text"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "format_text",
            "description": "Find text in the document and apply character formatting. Finds the FIRST occurrence of the search text and applies the specified formatting. Only the properties you include will be changed; omitted properties are left as-is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Exact text to find and format"},
                    "bold": {"type": "boolean", "description": "Set text to bold (true) or not bold (false)"},
                    "italic": {"type": "boolean", "description": "Set text to italic (true) or not italic (false)"},
                    "underline": {"type": "boolean", "description": "Set text to underlined (true) or not underlined (false)"},
                    "strikethrough": {"type": "boolean", "description": "Set text to strikethrough (true) or remove strikethrough (false)"},
                    "font_size": {"type": "number", "description": "Font size in points, e.g. 12.0, 14.0, 24.0"},
                    "font_color": {"type": "string", "description": "Font color as hex RGB string, e.g. '#FF0000' for red, '#0000FF' for blue"}
                },
                "required": ["search"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_paragraph_style",
            "description": "Find paragraphs containing the given text and set their paragraph style. Common styles: 'Heading 1' through 'Heading 6', 'Text Body', 'List Bullet', 'List Number', 'Quotations', 'Default Paragraph Style'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Text contained in the paragraph(s) to restyle"},
                    "style_name": {"type": "string", "description": "Paragraph style name, e.g. 'Heading 1', 'Text Body', 'List Bullet'"},
                    "all_matches": {"type": "boolean", "description": "Apply to all matching paragraphs (true) or just the first (false). Default false."}
                },
                "required": ["search", "style_name"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_text",
            "description": "Get the full text content of the document. Use max_chars to limit the size for large documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {"type": "integer", "description": "Maximum number of characters to return. Omit for the full document."}
                },
                "additionalProperties": False
            }
        }
    },
]


# ---------------------------------------------------------------------------
# Tool executor functions
# Each receives (model, ctx, args) where model is the XTextDocument,
# ctx is the UNO ComponentContext, and args is the parsed JSON arguments dict.
# Returns a JSON string with the result.
# ---------------------------------------------------------------------------

def tool_replace_text(model, ctx, args):
    """Find first occurrence and replace."""
    sd = model.createSearchDescriptor()
    sd.SearchString = args["search"]
    sd.SearchRegularExpression = False
    sd.SearchCaseSensitive = True
    found = model.findFirst(sd)
    if found:
        found.setString(args["replacement"])
        return json.dumps({"status": "ok", "message": "Replaced 1 occurrence."})
    return json.dumps({"status": "not_found", "message": "Text not found in document."})


def tool_search_and_replace_all(model, ctx, args):
    """Replace all occurrences."""
    rd = model.createReplaceDescriptor()
    rd.SearchString = args["search"]
    rd.ReplaceString = args["replacement"]
    rd.SearchCaseSensitive = args.get("case_sensitive", True)
    rd.SearchRegularExpression = False
    count = model.replaceAll(rd)
    return json.dumps({"status": "ok", "message": "Replaced %d occurrence(s)." % count})


def tool_insert_text(model, ctx, args):
    """Insert text at a position."""
    text_obj = model.getText()
    position = args["position"]
    insert_str = args["text"]

    if position == "beginning":
        cursor = text_obj.createTextCursor()
        cursor.gotoStart(False)
        text_obj.insertString(cursor, insert_str, False)
    elif position == "end":
        cursor = text_obj.createTextCursor()
        cursor.gotoEnd(False)
        text_obj.insertString(cursor, insert_str, False)
    elif position in ("before_selection", "after_selection"):
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            rng = sel.getByIndex(0)
            anchor = rng.getStart() if position == "before_selection" else rng.getEnd()
            cursor = text_obj.createTextCursorByRange(anchor)
            text_obj.insertString(cursor, insert_str, False)
        else:
            # No selection -- fall back to end of document
            cursor = text_obj.createTextCursor()
            cursor.gotoEnd(False)
            text_obj.insertString(cursor, insert_str, False)
    else:
        return json.dumps({"status": "error", "message": "Unknown position: %s" % position})

    return json.dumps({"status": "ok", "message": "Inserted text at %s." % position})


def tool_get_selection(model, ctx, args):
    """Return currently selected text."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            selected = sel.getByIndex(0).getString()
            return json.dumps({"status": "ok", "text": selected})
    except Exception:
        pass
    return json.dumps({"status": "ok", "text": ""})


def tool_replace_selection(model, ctx, args):
    """Replace selected text."""
    try:
        sel = model.getCurrentController().getSelection()
        if sel and sel.getCount() > 0:
            rng = sel.getByIndex(0)
            old_len = len(rng.getString())
            rng.setString(args["new_text"])
            return json.dumps({"status": "ok", "message": "Replaced selection (%d chars)." % old_len})
    except Exception:
        pass
    return json.dumps({"status": "no_selection", "message": "No text is selected."})


def tool_format_text(model, ctx, args):
    """Find text and apply character formatting."""
    sd = model.createSearchDescriptor()
    sd.SearchString = args["search"]
    sd.SearchRegularExpression = False
    sd.SearchCaseSensitive = True
    found = model.findFirst(sd)
    if not found:
        return json.dumps({"status": "not_found", "message": "Text not found in document."})

    applied = []

    if "bold" in args:
        # com.sun.star.awt.FontWeight: NORMAL=100, BOLD=150
        found.setPropertyValue("CharWeight", 150.0 if args["bold"] else 100.0)
        applied.append("bold" if args["bold"] else "unbold")

    if "italic" in args:
        # com.sun.star.awt.FontSlant: NONE=0, ITALIC=2
        from com.sun.star.awt.FontSlant import ITALIC, NONE as SLANT_NONE
        found.setPropertyValue("CharPosture", ITALIC if args["italic"] else SLANT_NONE)
        applied.append("italic" if args["italic"] else "unitalic")

    if "underline" in args:
        # com.sun.star.awt.FontUnderline: NONE=0, SINGLE=1
        found.setPropertyValue("CharUnderline", 1 if args["underline"] else 0)
        applied.append("underline" if args["underline"] else "no underline")

    if "strikethrough" in args:
        # com.sun.star.awt.FontStrikeout: NONE=0, SINGLE=1
        found.setPropertyValue("CharStrikeout", 1 if args["strikethrough"] else 0)
        applied.append("strikethrough" if args["strikethrough"] else "no strikethrough")

    if "font_size" in args:
        found.setPropertyValue("CharHeight", float(args["font_size"]))
        applied.append("size %spt" % args["font_size"])

    if "font_color" in args:
        hex_color = str(args["font_color"]).lstrip("#")
        color_int = int(hex_color, 16)
        found.setPropertyValue("CharColor", color_int)
        applied.append("color #%s" % hex_color)

    if not applied:
        return json.dumps({"status": "ok", "message": "Text found but no formatting properties specified."})

    return json.dumps({"status": "ok", "message": "Applied %s to '%s'." % (", ".join(applied), args["search"])})


def tool_set_paragraph_style(model, ctx, args):
    """Set paragraph style on paragraphs containing search text."""
    style_name = args["style_name"]
    all_matches = args.get("all_matches", False)
    search_text = args["search"]

    text_obj = model.getText()
    enum = text_obj.createEnumeration()
    count = 0
    while enum.hasMoreElements():
        para = enum.nextElement()
        # Skip text tables and other non-paragraph content
        if not hasattr(para, "getString"):
            continue
        if search_text in para.getString():
            try:
                para.setPropertyValue("ParaStyleName", style_name)
                count += 1
            except Exception as e:
                return json.dumps({"status": "error", "message": "Style '%s' not found or error: %s" % (style_name, e)})
            if not all_matches:
                break

    if count == 0:
        return json.dumps({"status": "not_found", "message": "No paragraph containing '%s' found." % search_text})
    return json.dumps({"status": "ok", "message": "Applied '%s' to %d paragraph(s)." % (style_name, count)})


def tool_get_document_text(model, ctx, args):
    """Get full document text."""
    text_obj = model.getText()
    cursor = text_obj.createTextCursor()
    cursor.gotoStart(False)
    cursor.gotoEnd(True)
    full_text = cursor.getString()
    max_chars = args.get("max_chars")
    if max_chars and len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n\n[... truncated ...]"
    return json.dumps({"status": "ok", "text": full_text, "length": len(full_text)})


# ---------------------------------------------------------------------------
# Tool dispatch table
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "replace_text": tool_replace_text,
    "search_and_replace_all": tool_search_and_replace_all,
    "insert_text": tool_insert_text,
    "get_selection": tool_get_selection,
    "replace_selection": tool_replace_selection,
    "format_text": tool_format_text,
    "set_paragraph_style": tool_set_paragraph_style,
    "get_document_text": tool_get_document_text,
}


def execute_tool(tool_name, arguments, model, ctx):
    """Execute a tool by name. Returns JSON result string."""
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return json.dumps({"status": "error", "message": "Unknown tool: %s" % tool_name})
    try:
        return func(model, ctx, arguments)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
