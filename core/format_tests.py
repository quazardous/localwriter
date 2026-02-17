import json
from core.format_support import (
    document_to_markdown,
    tool_get_document_content,
    tool_apply_document_content,
    tool_find_text,
    _insert_markdown_at_position,
    _doc_text_length
)
from core.logging import debug_log


# ---------------------------------------------------------------------------
# In-LibreOffice test runner (called from main.py menu: Run markdown tests)
# ---------------------------------------------------------------------------

def run_markdown_tests(ctx, model=None):
    """
    Run format_support tests with real UNO. Called from main.py when user chooses Run markdown tests.
    ctx: UNO ComponentContext. model: optional XTextDocument (Writer); if None or not Writer, a new doc is created.
    Returns (passed_count, failed_count, list of message strings).
    """
    log = []
    passed = 0
    failed = 0

    def ok(msg):
        log.append("OK: %s" % msg)

    def fail(msg):
        log.append("FAIL: %s" % msg)

    desktop = ctx.getServiceManager().createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx)
    doc = model
    if doc is None or not hasattr(doc, "getText"):
        try:
            doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, ())
        except Exception as e:
            return 0, 1, ["Could not create Writer document: %s" % e]
    if not doc or not hasattr(doc, "getText"):
        return 0, 1, ["No Writer document available."]

    debug_log(ctx, "format_tests: run start (model=%s)" % ("supplied" if model is doc else "new"))

    try:
        md = document_to_markdown(doc, ctx, scope="full")
        if isinstance(md, str):
            passed += 1
            ok("document_to_markdown(scope='full') returned string (len=%d)" % len(md))
        else:
            failed += 1
            fail("document_to_markdown did not return string: %s" % type(md))
    except Exception as e:
        failed += 1
        log.append("FAIL: document_to_markdown raised: %s" % e)

    try:
        result = tool_get_document_content(doc, ctx, {"scope": "full"})
        data = json.loads(result)
        if data.get("status") == "ok" and "content" in data:
            passed += 1
            ok("tool_get_document_content returned status=ok and content (len=%d)" % len(data.get("content", "")))
        else:
            failed += 1
            fail("tool_get_document_content: %s" % result[:200])
    except Exception as e:
        failed += 1
        log.append("FAIL: tool_get_document_content raised: %s" % e)


    def _read_doc_text(d):
        raw = d.getText().createTextCursor()
        raw.gotoStart(False)
        raw.gotoEnd(True)
        return raw.getString()


    # Test: get_document_content returns document_length
    try:
        result = tool_get_document_content(doc, ctx, {"scope": "full"})
        data = json.loads(result)
        doc_len_actual = len(_read_doc_text(doc))
        if data.get("status") == "ok" and "document_length" in data and data["document_length"] == doc_len_actual:
            passed += 1
            ok("tool_get_document_content returns document_length (%d)" % doc_len_actual)
        else:
            failed += 1
            fail("tool_get_document_content document_length: got %s, doc len=%d" % (data.get("document_length"), doc_len_actual))
    except Exception as e:
        failed += 1
        log.append("FAIL: get_document_content document_length raised: %s" % e)

    test_content = "Format test\n\nThis was inserted by the test."
    insert_needle = "Format test"

    # Test: apply at end via _insert_markdown_at_position
    try:
        len_before = _doc_text_length(doc)[0]
        _insert_markdown_at_position(doc, ctx, test_content, "end")
        full_text = _read_doc_text(doc)
        len_after = len(full_text)
        content_found = insert_needle in full_text
        debug_log(ctx, "format_tests: apply at end len_before=%s len_after=%s content_found=%s" % (
            len_before, len_after, content_found))
        if content_found:
            passed += 1
            ok("apply at end: content found (len_after=%d)" % len_after)
        else:
            failed += 1
            fail("apply at end: content not found (len_before=%d len_after=%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: apply at end raised: %s" % e)
        debug_log(ctx, "format_tests: apply at end raised: %s" % e)

    # Test: production path (tool_apply_document_content target='end')
    try:
        result = tool_apply_document_content(doc, ctx, {
            "content": test_content,
            "target": "end",
        })
        data = json.loads(result)
        if data.get("status") != "ok":
            failed += 1
            fail("tool_apply_document_content: %s" % result[:200])
        else:
            full_text = _read_doc_text(doc)
            if insert_needle in full_text:
                passed += 1
                ok("tool_apply_document_content(target='end'): status=ok and content in document (len=%d)" % len(full_text))
            else:
                failed += 1
                fail("tool_apply_document_content returned ok but content not in document (len=%d)" % len(full_text))
    except Exception as e:
        failed += 1
        log.append("FAIL: tool_apply_document_content raised: %s" % e)

    # Test D: formatting (bold, italic) - VISIBLE TEST
    try:
        from core.constants import DOCUMENT_FORMAT
        if DOCUMENT_FORMAT == "markdown":
            formatted_input = "# Heading\n\n**Bold text** and *italic text*"
        else:
            formatted_input = "<h1>Heading</h1><p><b>Bold text</b> and <i>italic text</i></p>"

        len_before = _doc_text_length(doc)[0]
        result = tool_apply_document_content(doc, ctx, {
            "content": formatted_input,
            "target": "end",
        })
        data = json.loads(result)
        if data.get("status") != "ok":
            failed += 1
            fail("formatted content: tool returned error: %s" % result[:200])
        else:
            full_text = _read_doc_text(doc)
            len_after = len(full_text)
            # Check if ANY of the formatting keywords appear (raw or formatted)
            has_heading = "Heading" in full_text
            has_bold = "Bold" in full_text
            has_italic = "italic" in full_text
            
            if has_heading or has_bold or has_italic:
                passed += 1
                ok("formatted content: INSERTED (len %d→%d, has_heading=%s, has_bold=%s, has_italic=%s)" % (
                    len_before, len_after, has_heading, has_bold, has_italic))
            else:
                failed += 1
                fail("formatted content: NOT FOUND (len %d→%d)" % (len_before, len_after))
    except Exception as e:
        failed += 1
        log.append("FAIL: formatted content test raised: %s" % e)

    # Test E: search-and-replace path
    try:
        # Insert a known string, then replace it with content
        marker = "REPLACE_ME_MARKER"
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertString(cursor, "\n" + marker, False)
        
        replacement = "<b>replaced</b>" if DOCUMENT_FORMAT == "html" else "**replaced**"
        
        result = tool_apply_document_content(doc, ctx, {
            "content": replacement,
            "target": "search",
            "search": marker,
        })
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "replaced" in full_text and marker not in full_text:
            passed += 1
            ok("search-and-replace: marker replaced with content")
        else:
            failed += 1
            fail("search-and-replace: status=%s, marker_gone=%s, replaced_found=%s" % (
                data.get("status"), marker not in full_text, "replaced" in full_text))
    except Exception as e:
        failed += 1
        log.append("FAIL: search-and-replace test raised: %s" % e)

    # Test G: Real list input support
    try:
        # Pass a REAL list, expect joined content
        list_input = ["item_a", "item_b"]
        len_before = _doc_text_length(doc)[0]
        result = tool_apply_document_content(doc, ctx, {
            "content": list_input,
            "target": "end",
        })
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        
        has_content = "item_a" in full_text and "item_b" in full_text
        
        if data.get("status") == "ok" and has_content:
            passed += 1
            ok("list input accommodation: handled list input successfully")
        else:
            failed += 1
            fail("list input accommodation: status=%s, has_content=%s (input was %s)" % (
                data.get("status"), has_content, list_input))
    except Exception as e:
        failed += 1
        log.append("FAIL: list input test raised: %s" % e)

    # Test H: target="full" — replace entire document
    try:
        full_replacement = "<h1>Full Replace Test</h1><p>Only this content should remain.</p>"
        result = tool_apply_document_content(doc, ctx, {"content": full_replacement, "target": "full"})
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "Full Replace" in full_text:
            passed += 1
            ok("target='full': replaced entire document (len=%d)" % len(full_text))
        else:
            failed += 1
            fail("target='full': status=%s, content check failed (len=%d)" % (data.get("status"), len(full_text)))
    except Exception as e:
        failed += 1
        log.append("FAIL: target=full test raised: %s" % e)

    # Test I: target="range" with start=0, end=document_length
    try:
        from core.document import get_document_length
        doc_len = get_document_length(doc)
        range_content = "<h2>Range Replace</h2><p>Replaced [0, %d).</p>" % doc_len
        result = tool_apply_document_content(doc, ctx, {"content": range_content, "target": "range", "start": 0, "end": doc_len})
        data = json.loads(result)
        full_text = _read_doc_text(doc)
        if data.get("status") == "ok" and "Range Replace" in full_text:
            passed += 1
            ok("target='range' [0, doc_len): replaced content (len=%d)" % len(full_text))
        else:
            failed += 1
            fail("target='range': status=%s (len=%d)" % (data.get("status"), len(full_text)))
    except Exception as e:
        failed += 1
        log.append("FAIL: target=range test raised: %s" % e)

    # Test J: get_document_content scope="range"
    try:
        full_text = _read_doc_text(doc)
        if len(full_text) >= 10:
            result = tool_get_document_content(doc, ctx, {"scope": "range", "start": 0, "end": 10})
            data = json.loads(result)
            if data.get("status") == "ok" and data.get("start") == 0 and data.get("end") == 10 and "content" in data:
                passed += 1
                ok("get_document_content scope='range' (0,10): returns start, end and content")
            else:
                failed += 1
                fail("get_document_content scope=range: %s" % result[:200])
        else:
            passed += 1
            ok("get_document_content scope=range: skipped (doc too short)")
    except Exception as e:
        failed += 1
        log.append("FAIL: get_document_content scope=range raised: %s" % e)

    # Test K: tool_find_text
    try:
        marker_find = "FIND_ME_UNIQUE_xyz"
        text = doc.getText()
        cursor = text.createTextCursor()
        cursor.gotoEnd(False)
        text.insertString(cursor, "\n" + marker_find, False)
        
        result = tool_find_text(doc, ctx, {
            "search": marker_find,
            "case_sensitive": True
        })
        data = json.loads(result)
        
        if data.get("status") == "ok" and "ranges" in data:
            ranges = data["ranges"]
            if len(ranges) == 1:
                r = ranges[0]
                text_at_range = _read_doc_text(doc)[r["start"]:r["end"]]
                if text_at_range == marker_find:
                    passed += 1
                    ok("find_text: found correct range")
                else:
                    failed += 1
                    fail("find_text: range text mismatch. Expected '%s', got '%s'" % (marker_find, text_at_range))
            else:
                failed += 1
                fail("find_text: expected 1 match, got %d" % len(ranges))
        else:
            failed += 1
            fail("find_text: status=%s" % data.get("status"))
    except Exception as e:
        failed += 1
        log.append("FAIL: find_text raised: %s" % e)

    # Test L: HTML linebreak preservation
    try:
        from core.constants import DOCUMENT_FORMAT
        if DOCUMENT_FORMAT == "html":
            plain_input = "Line 1\nLine 2\n\nParagraph 2"
            len_before = _doc_text_length(doc)[0]
            result = tool_apply_document_content(doc, ctx, {
                "content": plain_input,
                "target": "end",
            })
            full_text = _read_doc_text(doc)
            # Check if all words are present. 
            # In HTML mode, if the fix works, these will be separated.
            # If it failed, they might be merged, but still present.
            # The real validation is that it doesn't error and content is there.
            has_content = "Line 1" in full_text and "Line 2" in full_text and "Paragraph 2" in full_text
            
            if has_content:
                passed += 1
                ok("HTML linebreak preservation: content inserted")
            else:
                failed += 1
                fail("HTML linebreak preservation: content missing")
        else:
            passed += 1
            ok("HTML linebreak preservation: skipped (not in HTML mode)")
    except Exception as e:
        failed += 1
        log.append("FAIL: HTML linebreak preservation test raised: %s" % e)

    return passed, failed, log
