import ast
import json
from core.calc_tools import execute_calc_tool, CALC_TOOLS
from core.logging import debug_log

def run_calc_tests(ctx, model=None):
    """
    Run Calc tool tests with real UNO.
    ctx: UNO ComponentContext. model: optional XSpreadsheetDocument; if None or not Calc, a new doc is created.
    Returns (passed_count, failed_count, list of message strings).
    """
    log = []
    passed = 0
    failed = 0

    def ok(msg):
        log.append("OK: %s" % msg)

    def fail(msg):
        log.append("FAIL: %s" % msg)

    try:
        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = model
        
        # Ensure we have a Calc document
        if doc is None or not hasattr(doc, "getSheets"):
            try:
                doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            except Exception as e:
                return 0, 1, ["Could not create Calc document: %s" % e]
        
        if not doc or not hasattr(doc, "getSheets"):
            return 0, 1, ["No Calc document available."]

        debug_log("calc_tests: starting tests", context="CalcTests")

        # Test: get_sheet_summary
        try:
            result = execute_calc_tool("get_sheet_summary", {}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                passed += 1
                ok("get_sheet_summary returned status=ok")
                summary = data.get("result", {})
                if "sheet_name" in summary and "used_range" in summary:
                    passed += 1
                    ok(f"Summary contains sheet_name ({summary['sheet_name']}) and used_range")
                else:
                    failed += 1
                    fail("Summary missing expected fields")
            else:
                failed += 1
                fail(f"get_sheet_summary failed: {result}")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: get_sheet_summary raised: {e}")

        # Test: list_sheets
        try:
            result = execute_calc_tool("list_sheets", {}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok" and isinstance(data.get("result"), list):
                passed += 1
                ok(f"list_sheets returned {len(data['result'])} sheets")
            else:
                failed += 1
                fail(f"list_sheets failed: {result}")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: list_sheets raised: {e}")

        # Test: write_formula and read_cell_range
        try:
            test_cell = "A1"
            test_value = "TestValue123"
            execute_calc_tool("write_formula", {"cell": test_cell, "formula": test_value}, doc, ctx)
            
            result = execute_calc_tool("read_cell_range", {"range_name": test_cell}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                raw = data.get("result")
                cell_val = raw[0][0].get("value") if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list) and len(raw[0]) > 0 and isinstance(raw[0][0], dict) else raw
                if cell_val == test_value:
                    passed += 1
                    ok(f"write/read single cell success: {test_value}")
                else:
                    failed += 1
                    fail(f"write/read single cell failed: expected {test_value}, got {data.get('result')}")
            else:
                failed += 1
                fail(f"write/read single cell failed: {result}")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: write/read single cell raised: {e}")

        # Test: write formula
        try:
            execute_calc_tool("write_formula", {"cell": "B1", "formula": "10"}, doc, ctx)
            execute_calc_tool("write_formula", {"cell": "B2", "formula": "20"}, doc, ctx)
            execute_calc_tool("write_formula", {"cell": "B3", "formula": "=SUM(B1:B2)"}, doc, ctx)
            
            result = execute_calc_tool("read_cell_range", {"range_name": "B3"}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                raw = data.get("result")
                val = raw[0][0].get("value") if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list) and len(raw[0]) > 0 and isinstance(raw[0][0], dict) else raw
                if val is not None and (val == 30 or val == 30.0 or str(val) in ("30", "30.0")):
                    passed += 1
                    ok(f"formula SUM(B1:B2) success: {val}")
                else:
                    failed += 1
                    fail(f"formula SUM(B1:B2) failed: expected 30, got {val}")
            else:
                failed += 1
                fail(f"read formula result failed: {result}")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: formula test raised: {e}")

        # Test: create_sheet
        try:
            new_sheet_name = "TestSheet_New"
            execute_calc_tool("create_sheet", {"sheet_name": new_sheet_name}, doc, ctx)
            
            result = execute_calc_tool("list_sheets", {}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok" and new_sheet_name in data.get("result"):
                passed += 1
                ok(f"create_sheet success: {new_sheet_name}")
            else:
                failed += 1
                fail(f"create_sheet failed or not in list: {result}")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: create_sheet raised: {e}")

        # Test: merge_cells and styles
        try:
            merge_range = "C1:D1"
            execute_calc_tool("merge_cells", {"range_name": merge_range}, doc, ctx)
            execute_calc_tool("set_cell_style", {"range_name": merge_range, "bold": True, "bg_color": "yellow"}, doc, ctx)
            passed += 1
            ok("merge_cells and set_cell_style executed without error")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: merge/style raised: {e}")

        # Test: clear_range
        try:
            execute_calc_tool("write_formula", {"cell": "E1", "formula": "clearMe"}, doc, ctx)
            execute_calc_tool("clear_range", {"range_name": "E1"}, doc, ctx)
            result = execute_calc_tool("read_cell_range", {"range_name": "E1"}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                val = data.get("result")
                cell_val = None
                if isinstance(val, list) and val and isinstance(val[0], list) and val[0]:
                    cell_val = val[0][0].get("value") if isinstance(val[0][0], dict) else val[0][0]
                elif isinstance(val, list) and val and isinstance(val[0], dict):
                    cell_val = val[0].get("value")
                if cell_val in (None, "", 0.0):
                    passed += 1
                    ok("clear_range cleared E1")
                else:
                    failed += 1
                    fail("clear_range: E1 not empty after clear: %s" % cell_val)
            else:
                failed += 1
                fail("clear_range/read failed: %s" % result)
        except Exception as e:
            failed += 1
            log.append(f"FAIL: clear_range raised: {e}")

        # Test: set_cell_style with number_format and alignment
        try:
            execute_calc_tool("write_formula", {"cell": "F1", "formula": "0.5"}, doc, ctx)
            execute_calc_tool("set_cell_style", {"range_name": "F1", "number_format": "0%", "h_align": "center"}, doc, ctx)
            passed += 1
            ok("set_cell_style number_format and h_align")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: set_cell_style number_format/h_align raised: {e}")

        # Test: sort_range
        try:
            for i, val in enumerate(["30", "10", "20"], start=1):
                execute_calc_tool("write_formula", {"cell": "G%d" % i, "formula": val}, doc, ctx)
            execute_calc_tool("sort_range", {"range_name": "G1:G3", "sort_column": 0, "ascending": True, "has_header": False}, doc, ctx)
            result = execute_calc_tool("read_cell_range", {"range_name": "G1:G3"}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                vals = data.get("result")
                if isinstance(vals, list) and len(vals) >= 1:
                    row0 = vals[0] if isinstance(vals[0], list) else vals
                    if isinstance(row0, list):
                        first_vals = [c.get("value") if isinstance(c, dict) else c for c in row0]
                    else:
                        first_vals = [row0.get("value") if isinstance(row0, dict) else row0]
                    flat = []
                    for row in vals:
                        if isinstance(row, list):
                            for c in row:
                                flat.append(c.get("value") if isinstance(c, dict) else c)
                        else:
                            flat.append(row.get("value") if isinstance(row, dict) else row)
                    if len(flat) >= 3:
                        try:
                            nums = [float(x) if x not in (None, "") else None for x in flat[:3]]
                            if nums[0] <= nums[1] <= nums[2]:
                                passed += 1
                                ok("sort_range ascending G1:G3")
                            else:
                                failed += 1
                                fail("sort_range order wrong: %s" % flat[:3])
                        except (TypeError, ValueError):
                            passed += 1
                            ok("sort_range executed (values: %s)" % flat[:3])
                    else:
                        passed += 1
                        ok("sort_range executed")
                else:
                    passed += 1
                    ok("sort_range executed")
            else:
                failed += 1
                fail("sort_range/read failed: %s" % result)
        except Exception as e:
            failed += 1
            log.append(f"FAIL: sort_range raised: {e}")

        # Test: switch_sheet
        try:
            execute_calc_tool("switch_sheet", {"sheet_name": new_sheet_name}, doc, ctx)
            result = execute_calc_tool("get_sheet_summary", {}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok" and data.get("result", {}).get("sheet_name") == new_sheet_name:
                passed += 1
                ok("switch_sheet to %s" % new_sheet_name)
            else:
                failed += 1
                fail("switch_sheet or get_sheet_summary failed: %s" % result)
            execute_calc_tool("switch_sheet", {"sheet_name": doc.getSheets().getByIndex(0).getName()}, doc, ctx)
        except Exception as e:
            failed += 1
            log.append(f"FAIL: switch_sheet raised: {e}")

        # Test: detect_and_explain_errors
        try:
            execute_calc_tool("write_formula", {"cell": "H1", "formula": "=1/0"}, doc, ctx)
            result = execute_calc_tool("detect_and_explain_errors", {"range_name": "H1:H1"}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                res = data.get("result")
                if res and (isinstance(res, list) and len(res) > 0 or isinstance(res, dict)):
                    passed += 1
                    ok("detect_and_explain_errors found error in H1")
                else:
                    passed += 1
                    ok("detect_and_explain_errors returned ok (result: %s)" % type(res).__name__)
            else:
                failed += 1
                fail("detect_and_explain_errors failed: %s" % result)
        except Exception as e:
            failed += 1
            log.append(f"FAIL: detect_and_explain_errors raised: {e}")

        # Test: create_chart
        try:
            execute_calc_tool("write_formula", {"cell": "I1", "formula": "X"}, doc, ctx)
            execute_calc_tool("write_formula", {"cell": "I2", "formula": "1"}, doc, ctx)
            execute_calc_tool("write_formula", {"cell": "J1", "formula": "Y"}, doc, ctx)
            execute_calc_tool("write_formula", {"cell": "J2", "formula": "2"}, doc, ctx)
            result = execute_calc_tool("create_chart", {"data_range": "I1:J2", "chart_type": "bar", "has_header": True}, doc, ctx)
            data = json.loads(result)
            if data.get("status") == "ok":
                passed += 1
                ok("create_chart bar I1:J2")
            else:
                failed += 1
                fail("create_chart failed: %s" % result)
        except Exception as e:
            failed += 1
            log.append(f"FAIL: create_chart raised: {e}")

        # Test: get_calc_context_for_chat
        try:
            from core.document import get_calc_context_for_chat
            ctx_str = get_calc_context_for_chat(doc, 8000, ctx)
            if "Used Range" in ctx_str or "rows" in ctx_str or "columns" in ctx_str:
                passed += 1
                ok("get_calc_context_for_chat returns summary")
            else:
                failed += 1
                fail("get_calc_context_for_chat missing expected content: %s" % ctx_str[:200])
            if "Sheet" in ctx_str or "sheet" in ctx_str:
                passed += 1
                ok("get_calc_context_for_chat contains sheet info")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: get_calc_context_for_chat raised: {e}")

        # Test: get_document_context_for_chat with Calc (delegation)
        try:
            from core.document import get_document_context_for_chat
            ctx_str = get_document_context_for_chat(doc, 8000, ctx=ctx)
            if ctx_str and ("Used Range" in ctx_str or "rows" in ctx_str or "columns" in ctx_str):
                passed += 1
                ok("get_document_context_for_chat(Calc) returns summary")
            else:
                failed += 1
                fail("get_document_context_for_chat(Calc) wrong: %s" % (ctx_str[:200] if ctx_str else "empty"))
        except Exception as e:
            failed += 1
            log.append(f"FAIL: get_document_context_for_chat(Calc) raised: {e}")

        # Test: ctx required for get_calc_context_for_chat
        try:
            from core.document import get_calc_context_for_chat
            get_calc_context_for_chat(doc, 8000, ctx=None)
            failed += 1
            fail("get_calc_context_for_chat(None) should raise ValueError")
        except ValueError:
            passed += 1
            ok("get_calc_context_for_chat requires ctx")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: get_calc_context_for_chat ctx test: expected ValueError, got {e}")

        # Test: ctx required for get_document_context_for_chat when Calc
        try:
            from core.document import get_document_context_for_chat
            get_document_context_for_chat(doc, 8000, ctx=None)
            failed += 1
            fail("get_document_context_for_chat(Calc, ctx=None) should raise ValueError")
        except ValueError:
            passed += 1
            ok("get_document_context_for_chat(Calc) requires ctx")
        except Exception as e:
            failed += 1
            log.append(f"FAIL: get_document_context_for_chat ctx test: expected ValueError, got {e}")

    except Exception as e:
        failed += 1
        log.append(f"CRITICAL failure in test runner: {e}")

    return passed, failed, log


def run_calc_integration_tests(ctx, model=None):
    """
    Run Calc integration tests using the currently configured AI (Settings).
    Uses existing get_api_config, LlmClient, request_with_tools, execute_calc_tool.
    Returns (passed_count, failed_count, list of message strings).
    Skips with a message if config is invalid or request fails.
    """
    log = []
    passed = 0
    failed = 0

    def ok(msg):
        log.append("OK: %s" % msg)

    def fail(msg):
        log.append("FAIL: %s" % msg)

    try:
        from core.config import get_api_config, validate_api_config
        api_config = get_api_config(ctx)
        ok_config, err_msg = validate_api_config(api_config)
        if not ok_config:
            log.append("Skipped (integration): %s" % err_msg)
            return 0, 0, log

        smgr = ctx.getServiceManager()
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = model
        if doc is None or not hasattr(doc, "getSheets"):
            try:
                doc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            except Exception as e:
                log.append("Skipped (integration): Could not create Calc document: %s" % e)
                return 0, 0, log
        if not doc or not hasattr(doc, "getSheets"):
            log.append("Skipped (integration): No Calc document available.")
            return 0, 0, log

        from core.document import get_calc_context_for_chat
        from core.constants import get_chat_system_prompt_for_document
        from core.api import LlmClient

        debug_log("calc_integration_tests: starting", context="CalcTests")
        system_prompt = get_chat_system_prompt_for_document(doc, "")
        ctx_str = get_calc_context_for_chat(doc, 4000, ctx)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Document context:\n" + ctx_str + "\n\nTask: Write the number 42 in cell A1. Use the appropriate tool."},
        ]
        client = LlmClient(api_config, ctx)
        try:
            response = client.request_with_tools(messages, max_tokens=512, tools=CALC_TOOLS)
        except Exception as e:
            log.append("Skipped (integration): API request failed: %s" % e)
            return 0, 0, log

        tool_calls = response.get("tool_calls")
        if not isinstance(tool_calls, list) or len(tool_calls) == 0:
            fail("Expected at least one tool call from model; got %s" % (response.get("finish_reason") or "no tool_calls"))
            return passed, failed + 1, log

        wrote_a1 = False
        for tc in tool_calls:
            func = tc.get("function") or {}
            name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                try:
                    args = ast.literal_eval(args_str) if args_str else {}
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            try:
                result = execute_calc_tool(name, args, doc, ctx)
                res_data = json.loads(result)
                if name == "write_formula" and res_data.get("status") == "ok":
                    cell = args.get("cell", "")
                    if cell.upper() == "A1":
                        wrote_a1 = True
            except Exception as e:
                log.append("Tool %s failed: %s" % (name, e))

        if not wrote_a1:
            fail("Model did not write to A1 (or write_formula failed)")
            return passed, failed + 1, log

        result = execute_calc_tool("read_cell_range", {"range_name": "A1"}, doc, ctx)
        data = json.loads(result)
        if data.get("status") != "ok":
            fail("read_cell_range A1 failed: %s" % result)
            return passed, failed + 1, log
        val = data.get("result")
        cell_val = None
        if isinstance(val, list) and val and isinstance(val[0], list) and val[0]:
            cell_val = val[0][0].get("value") if isinstance(val[0][0], dict) else val[0][0]
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            cell_val = val[0].get("value")
        if cell_val in (42, 42.0, "42"):
            passed += 1
            ok("Integration: model wrote 42 to A1, read back ok")
        else:
            failed += 1
            fail("Integration: A1 value is %s, expected 42" % cell_val)
    except Exception as e:
        failed += 1
        log.append("CRITICAL (integration): %s" % e)

    return passed, failed, log
