# MCP Tool Comparison Report: mcp-libre vs localwriter

**Date**: 2026-02-24
**mcp-libre tools**: 76 tools
**localwriter tools**: 41 tools

---

## Summary

| Category | Same Name Ported | Renamed | Merged | Missing |
|----------|-----------------|---------|--------|---------|
| Writer Nav/Tree | 5 | 0 | 0 | 0 |
| Writer Content/Editing | 3 | 0 | 0 | 5 |
| Writer Comments/Workflow | 4 | 0 | 0 | 4 |
| Writer Search | 2 | 1 | 0 | 1 |
| Writer Tables | 3 | 0 | 0 | 1 |
| Writer Styles | 2 | 0 | 0 | 0 |
| Writer Track Changes | 4 | 0 | 0 | 0 |
| Writer Structural | 3 | 0 | 0 | 3 |
| Writer Images/Frames | 0 | 0 | 0 | 10 |
| Document Lifecycle | 2 | 1 | 1 | 4 |
| Batch/Workflow | 1 | 0 | 0 | 1 |
| Calc | 1 | 1 | 0 | 2 |
| Impress | 0 | 0 | 0 | 3 |
| Diagnostics/Protection | 0 | 0 | 0 | 2 |

---

## Writer Navigation / Tree Tools

### get_document_tree
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `content_strategy` enum is `["none", "first_lines", "ai_summary_first", "full"]`, `depth` default 1, has `file_path`
  - localwriter: `content_strategy` enum is `["heading_only", "first_lines", "ai_summary_first", "full"]`, `depth` default 1 (0=unlimited), no `file_path`
  - `"none"` renamed to `"heading_only"` in localwriter
  - `file_path` param missing in localwriter (uses active doc only)
- **Implementation notes**: mcp-libre delegates to `services.writer.get_document_tree()` (tree service). localwriter delegates to `ctx.services.writer_tree.get_document_tree()`. Both build a heading tree with `_mcp_` bookmarks. localwriter returns `{"status": "ok", ...result}` while mcp-libre returns `{"success": True, ...}`. The underlying tree service logic is in `writer_nav/services/tree.py` (localwriter) vs `services/writer/tree.py` (mcp-libre) -- functionally equivalent.

### get_heading_children
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`, `content_strategy` enum uses `"none"`
  - localwriter: no `file_path`, `content_strategy` enum uses `"heading_only"`
  - Otherwise identical params (locator, heading_para_index, heading_bookmark, depth)
- **Implementation notes**: Both delegate to their respective tree services. Functionally equivalent.

### navigate_heading
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no `file_path`
  - Same direction enum, same required params
- **Implementation notes**: mcp-libre delegates to `services.writer.navigate_heading()`. localwriter delegates to `ctx.services.writer_proximity.navigate_heading()`. Both use cached heading tree for O(1) navigation. Functionally equivalent.

### get_surroundings
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `include` items has `enum` constraint on strings; has `file_path`
  - localwriter: `include` items are plain `string` type (no enum constraint); no `file_path`
- **Implementation notes**: Both delegate to proximity service. mcp-libre uses `services.writer.get_surroundings()`, localwriter uses `ctx.services.writer_proximity.get_surroundings()`. Functionally equivalent.

### read_paragraphs
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `locator`, `start_index` (legacy), `count`, `file_path`. `start_index` not required.
  - localwriter: has `start_index` (required), `count`. Missing `locator` and `file_path`.
  - **Missing in localwriter**: `locator` param (cannot read from bookmark/page/section locator)
- **Implementation notes**: mcp-libre supports unified locators (`paragraph:N`, `page:N`, `bookmark:_mcp_xxx`) and delegates to `services.writer.read_paragraphs()`. localwriter only supports numeric `start_index` and reads directly from `doc_svc.get_paragraph_ranges()`. localwriter is significantly less capable -- it cannot use bookmarks or page locators. `start_index` is required in localwriter but optional in mcp-libre.

---

## Writer Content / Editing Tools

### insert_at_paragraph
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `text` required, has `locator`, `paragraph_index` (legacy), `position` enum `["before", "after"]`, `style`, `file_path`
  - localwriter: `paragraph_index` required, `text` required, `position` enum `["before", "after", "replace"]`, no `locator`, no `style`, no `file_path`
  - **Missing in localwriter**: `locator`, `style`, `file_path`
  - **Added in localwriter**: `"replace"` position option
  - **Different defaults**: mcp-libre defaults to `"after"`, localwriter defaults to `"before"`
- **Implementation notes**: mcp-libre delegates to `services.writer.insert_at_paragraph()` which supports unified locators and styles. localwriter does inline UNO manipulation without locator support. mcp-libre's implementation is more sophisticated (bookmark support, style inheritance). localwriter adds "replace" mode not in mcp-libre.

### set_paragraph_text
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a dedicated tool to replace paragraph text while preserving style, returning `paragraph_index` and `bookmark` for batch chaining. No equivalent in localwriter. The `insert_at_paragraph` with `position="replace"` is a partial substitute but does not return paragraph_index/bookmark for batch variables.

### set_paragraph_style
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to change paragraph style by locator. No equivalent in localwriter.

### delete_paragraph
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to delete a paragraph by locator. No equivalent in localwriter.

### duplicate_paragraph
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to duplicate a paragraph (with style) after itself, with a `count` parameter for blocks. No equivalent in localwriter.

### clone_heading_block
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to clone an entire heading block (heading + sub-headings + body). No equivalent in localwriter.

### insert_paragraphs_batch
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to insert multiple paragraphs in one UNO transaction. No equivalent in localwriter.

### get_paragraph_count
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a dedicated tool. In localwriter, this info is available indirectly through `get_document_stats` which returns `paragraph_count`.

### get_page_count
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a dedicated tool. In localwriter, this info is available indirectly through `get_document_stats` which returns `page_count`.

---

## Writer Comments / Workflow Tools

### list_comments
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `author_filter`, `file_path`
  - localwriter: no params at all
  - **Missing in localwriter**: `author_filter`, `file_path`
- **Implementation notes**: mcp-libre delegates to `services.comments.list_comments()` and applies author filtering in the tool layer. localwriter reads annotations directly in the tool, building similar output. Both read Author, Content, Name, ParentName, Resolved, DateTimeValue. localwriter adds `anchor_preview` (80 char preview of anchor text). Functionally similar but localwriter lacks filtering.

### add_comment
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `content` required, has `author`, `locator`, `paragraph_index` (legacy), `file_path`
  - localwriter: `content` and `search_text` required, has `author`. Missing `locator`, `paragraph_index`, `file_path`
  - **Different approach**: mcp-libre anchors by paragraph locator/index; localwriter anchors by text search
  - **Missing in localwriter**: `locator`, `paragraph_index`, `file_path`
  - **Added in localwriter**: `search_text` (required)
- **Implementation notes**: Completely different anchoring strategy. mcp-libre places comment at a specific paragraph by locator. localwriter searches for text and anchors to the match. localwriter's approach is simpler but less precise (cannot target specific paragraphs without matching text).

### delete_comment
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `comment_name`, `author` (delete by author), `file_path`
  - localwriter: `comment_name` required. Missing `author`, `file_path`
  - **Missing in localwriter**: `author` (bulk delete by author), `file_path`
- **Implementation notes**: mcp-libre can delete by name OR by author (bulk delete). localwriter only deletes by name. Both delete the comment and its replies (via ParentName matching).

### resolve_comment
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to resolve a comment with a resolution message. No equivalent in localwriter.

### scan_tasks
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to scan comments for task prefixes (TODO-AI, FIX, QUESTION, etc.). No equivalent in localwriter.

### get_workflow_status
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to read the MCP-WORKFLOW dashboard comment. No equivalent in localwriter.

### set_workflow_status
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to create/update the workflow dashboard. No equivalent in localwriter.

---

## Writer Search Tools

### search_in_document
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a LibreOffice native search with paragraph context. localwriter has `find_text` which is similar but returns character offsets instead of paragraph context. See below.

### find_text (localwriter) vs search_in_document (mcp-libre)
- **Status**: localwriter `find_text` is a PARTIAL EQUIVALENT of mcp-libre `search_in_document`
- **Params diff**:
  - mcp-libre `search_in_document`: `pattern`, `regex`, `case_sensitive`, `max_results`, `context_paragraphs`, `file_path`
  - localwriter `find_text`: `search`, `start`, `limit`, `case_sensitive`
  - **Missing in localwriter**: `regex`, `context_paragraphs`, `file_path`
  - **Added in localwriter**: `start` (offset to search from)
- **Implementation notes**: mcp-libre returns matches with surrounding paragraph context and uses LO native search. localwriter returns `{start, end, text}` character ranges. Different output format -- mcp-libre is paragraph-oriented, localwriter is character-offset-oriented.

### replace_in_document
- **Status**: MISSING (but partially covered by `apply_document_content`)
- **Implementation notes**: mcp-libre has a dedicated find-and-replace tool with regex support. localwriter's `apply_document_content` with `target="search"` provides similar functionality but different interface. localwriter does not support regex in its search-replace. Both preserve formatting.

### search_boolean / search_fulltext
- **Status**: RENAMED_TO(search_fulltext)
- **Params diff**:
  - mcp-libre `search_boolean`: `query`, `max_results`, `context_paragraphs`, `around_page`, `page_radius`, `include_pages`, `file_path`
  - localwriter `search_fulltext`: `query`, `max_results`, `context_paragraphs`
  - **Missing in localwriter**: `around_page`, `page_radius`, `include_pages`, `file_path`
- **Implementation notes**: Both use Snowball stemming with boolean operators (AND, OR, NOT, NEAR/N). mcp-libre has page-proximity filtering (`around_page` + `page_radius`) and optional page number inclusion. localwriter lacks these page-aware features. Both delegate to their index services which are architecturally equivalent.

### get_index_stats
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params
  - **Missing in localwriter**: `file_path`
- **Implementation notes**: Both return paragraph count, unique stems, language, top 20 frequent stems. Functionally equivalent.

---

## Writer Table Tools

### list_tables
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params
  - **Missing in localwriter**: `file_path`
- **Implementation notes**: Both iterate `getTextTables()` and return name, rows, cols. Functionally equivalent.

### read_table
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `table_name` (required), `file_path`
  - localwriter: has `table_name` (required). Missing `file_path`
- **Implementation notes**: Both return 2D array of cell values. Both use `getCellByName()` with column letter conversion. Functionally equivalent.

### write_table_cell
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `table_name`, `cell`, `value` (all required), `file_path`
  - localwriter: has `table_name`, `cell`, `value` (all required). Missing `file_path`
- **Implementation notes**: Both auto-detect numbers. Both use `setCellByName()`. Functionally equivalent.

### create_table
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to create a new table at a paragraph position with locator support. No equivalent in localwriter.

---

## Writer Style Tools

### list_styles
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `family` is free-text string with description listing options; has `file_path`
  - localwriter: `family` has `enum` constraint with the 5 family names. Missing `file_path`
  - localwriter's enum constraint is more precise
- **Implementation notes**: Both iterate style family and return name, is_user_defined, is_in_use. localwriter also returns `parent_style`. Functionally equivalent.

### get_style_info
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `family` is free-text string; has `file_path`
  - localwriter: `family` has `enum` constraint. Missing `file_path`
- **Implementation notes**: Both return detailed style properties. localwriter reads from a fixed `_FAMILY_PROPS` dict per family; mcp-libre delegates to `services.styles.get_style_info()`. Functionally equivalent.

---

## Writer Track Changes Tools

### set_track_changes
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `enabled` required, `file_path`
  - localwriter: `enabled` required. Missing `file_path`
- **Implementation notes**: mcp-libre delegates to `services.comments.set_track_changes()`. localwriter sets `RecordChanges` property directly. Both set the UNO property. Functionally equivalent.

### get_tracked_changes
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both enumerate redlines and return type, author, date, comment. Functionally equivalent.

### accept_all_changes
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: mcp-libre delegates to `services.comments.accept_all_changes()`. localwriter uses UNO dispatcher with `.uno:AcceptAllTrackedChanges`. Both achieve the same result but via different UNO mechanisms. Functionally equivalent.

### reject_all_changes
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Same pattern as accept_all_changes. Functionally equivalent.

---

## Writer Structural Tools

### list_sections
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both iterate `getTextSections()`. localwriter returns `is_visible` and `is_protected` for each section. mcp-libre delegates to `services.writer.list_sections()`. Functionally equivalent; localwriter has slightly richer output.

### read_section
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to read the content of a named text section. No equivalent in localwriter.

### list_bookmarks
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both list bookmarks with anchor text previews. Functionally equivalent.

### resolve_bookmark
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to resolve a bookmark to its paragraph index. No equivalent in localwriter.

### refresh_indexes
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both iterate `getDocumentIndexes()` and call `update()`. Functionally equivalent.

### update_fields
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to refresh all text fields (dates, page numbers, cross-references). No equivalent in localwriter.

---

## Writer Image / Frame Tools

### list_images
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to list all images/graphic objects with name, dimensions, title, description. No equivalent in localwriter. localwriter has `generate_image` and `edit_image` for AI image generation but no image listing/management tools.

### get_image_info
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a detailed image inspection tool. No equivalent in localwriter.

### set_image_properties
- **Status**: MISSING
- **Implementation notes**: mcp-libre can resize, reposition, crop, and update captions. No equivalent in localwriter.

### download_image
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a URL-to-local-cache image downloader with retry and SSL bypass. No equivalent in localwriter.

### insert_image
- **Status**: MISSING
- **Implementation notes**: mcp-libre can insert images from file path or URL with frames and captions. localwriter has `generate_image` which generates and inserts, but no tool to insert an existing image file.

### delete_image
- **Status**: MISSING
- **Implementation notes**: mcp-libre can delete images and their parent frames. No equivalent in localwriter.

### replace_image
- **Status**: MISSING
- **Implementation notes**: mcp-libre can replace an image's source while keeping frame/position. No equivalent in localwriter.

### list_text_frames
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to list all text frames. No equivalent in localwriter.

### get_text_frame_info
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a detailed text frame inspection tool. No equivalent in localwriter.

### set_text_frame_properties
- **Status**: MISSING
- **Implementation notes**: mcp-libre can modify frame size, position, wrap, anchor. No equivalent in localwriter.

---

## Document Lifecycle Tools

### save_document
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path` (optional, to save a specific document)
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: mcp-libre can save any open document by path. localwriter can only save the active document (and rejects unsaved new documents). localwriter calls `doc.store()` directly; mcp-libre delegates to `services.base.store_doc()`. Functionally similar for the active-document case.

### get_document_properties / get_document_info
- **Status**: MERGED_INTO(get_document_info)
- **Params diff**:
  - mcp-libre `get_document_properties`: has `file_path`. Returns title, author, subject, keywords, dates.
  - localwriter `get_document_info`: no params. Returns title, author, subject, description, doc_type, file_url, is_modified, is_new.
  - **Missing in localwriter**: `file_path`, `keywords`, dates
  - **Added in localwriter**: `doc_type`, `file_url`, `is_modified`, `is_new`
- **Implementation notes**: Different scope. mcp-libre focuses purely on document properties (metadata). localwriter combines metadata with document state info. localwriter's `get_document_info` partially covers `get_document_properties` and `list_open_documents` use cases.

### set_document_properties
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to update title, author, subject, description, keywords. No equivalent in localwriter.

### create_document
- **Status**: MISSING
- **Implementation notes**: mcp-libre can create new writer/calc/impress/draw documents with optional initial content. No equivalent in localwriter.

### open_document
- **Status**: MISSING
- **Implementation notes**: mcp-libre can open a document by file path. No equivalent in localwriter.

### close_document
- **Status**: MISSING
- **Implementation notes**: mcp-libre can close a document by file path. No equivalent in localwriter.

### list_open_documents
- **Status**: MISSING
- **Implementation notes**: mcp-libre lists all open documents. No equivalent in localwriter (partially covered by get_document_info for active doc).

### save_document_as
- **Status**: MISSING
- **Implementation notes**: mcp-libre can save/duplicate a document under a new name. No equivalent in localwriter.

### get_recent_documents
- **Status**: MISSING
- **Implementation notes**: mcp-libre can get recently opened documents from LO history. No equivalent in localwriter.

---

## Writer Page Navigation Tools

### goto_page
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `page` required, `file_path`
  - localwriter: `page` required. Missing `file_path`
- **Implementation notes**: mcp-libre delegates to `services.writer.goto_page()`. localwriter uses `getCurrentController().getViewCursor().jumpToPage()` directly. Functionally equivalent.

### get_page_objects
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `page`, `locator`, `paragraph_index`, `file_path`
  - localwriter: has `page`, `locator`, `paragraph_index`. Missing `file_path`
- **Implementation notes**: Both scan images, tables, and frames on a given page. localwriter implements `_scan_page()` inline; mcp-libre delegates to service layer. localwriter resolves locators through `doc_svc.resolve_locator()`. Functionally equivalent.

---

## AI Annotation Tools

### add_ai_summary
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `summary` required, has `locator`, `para_index`, `file_path`
  - localwriter: `summary` required, has `locator`, `para_index`. Missing `file_path`
- **Implementation notes**: mcp-libre delegates to `services.writer.add_ai_summary()`. localwriter delegates to `ctx.services.writer_tree.add_ai_summary()` and resolves locators via `doc_svc.resolve_locator()`. Functionally equivalent.

### get_ai_summaries
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both list MCP-AI annotations. Functionally equivalent.

### remove_ai_summary
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `locator`, `para_index`, `file_path`
  - localwriter: has `locator`, `para_index`. Missing `file_path`
- **Implementation notes**: Both remove AI annotations by paragraph position. Functionally equivalent.

---

## Batch / Workflow Tools

### execute_batch
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: `operations` (with `revision_comment` per op), `stop_on_error`, `check_conditions`, `follow`, `revision_comment` (global)
  - localwriter: `operations` (no `revision_comment` per op), `stop_on_error`, `follow`
  - **Missing in localwriter**: `check_conditions`, `revision_comment` (both global and per-operation), per-operation `revision_comment` property
- **Implementation notes**: Both implement batch variable resolution ($last, $step.N, etc.), pre-flight validation, batch mode toggling, and follow mode. mcp-libre additionally checks human stop conditions between operations (`check_conditions`) and supports revision comments for tracked changes. mcp-libre validates via `server.tools` dict, localwriter via `ctx.services.tools` registry. mcp-libre checks `success` key; localwriter checks `status != "error"`. The batch variable resolution logic is identical in structure.

### check_stop_conditions
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a standalone tool to check human stop signals (STOP/CANCEL comments, workflow phase). No equivalent in localwriter. Related to the `check_conditions` feature missing from execute_batch.

---

## Calc Tools

### read_cells (mcp-libre) vs read_cell_range (localwriter)
- **Status**: RENAMED_TO(read_cell_range)
- **Params diff**:
  - mcp-libre `read_cells`: `range_str` (string, required), `file_path`
  - localwriter `read_cell_range`: `range_name` (string or array, required). Missing `file_path`
  - localwriter supports array of ranges for non-contiguous areas
  - localwriter's `range_name` is more flexible (array support)
- **Implementation notes**: mcp-libre delegates to `services.calc.read_cells()`. localwriter uses `CalcBridge` + `CellInspector.read_range()`. Different architecture but functionally equivalent for single ranges. localwriter adds multi-range support.

### write_cell (mcp-libre) vs write_formula_range (localwriter)
- **Status**: RENAMED_TO(write_formula_range)
- **Params diff**:
  - mcp-libre `write_cell`: `cell` (string), `value` (string), `file_path`. Single cell only.
  - localwriter `write_formula_range`: `range_name` (string or array), `formula_or_values` (string, number, or array). Range support, formula support.
  - localwriter is significantly more capable: range writes, formula support, array values
- **Implementation notes**: mcp-libre writes single cell values via `services.calc.write_cell()`. localwriter uses `CellManipulator.write_formula_range()` which can write to ranges, handle formulas (starting with `=`), and fill ranges with arrays. localwriter is a superset.

### list_sheets
- **Status**: SAME_NAME_PORTED
- **Params diff**:
  - mcp-libre: has `file_path`
  - localwriter: no params. Missing `file_path`
- **Implementation notes**: Both list sheet names. mcp-libre delegates to `services.calc.list_sheets()`. localwriter uses `CalcBridge` + `CellManipulator.list_sheets()`. Functionally equivalent.

### get_sheet_info (mcp-libre) vs get_sheet_summary (localwriter)
- **Status**: RENAMED_TO(get_sheet_summary)
- **Params diff**:
  - mcp-libre `get_sheet_info`: `sheet_name` (optional), `file_path`
  - localwriter `get_sheet_summary`: `sheet_name` (optional). Missing `file_path`
- **Implementation notes**: mcp-libre delegates to `services.calc.get_sheet_info()` returning used range and dimensions. localwriter uses `SheetAnalyzer.get_sheet_summary()` which may return richer info (column headers, etc.). Different names, similar purpose.

---

## Impress Tools

### list_slides
- **Status**: MISSING
- **Implementation notes**: mcp-libre has a tool to list all slides with names, layout, and titles. No equivalent in localwriter.

### read_slide_text
- **Status**: MISSING
- **Implementation notes**: mcp-libre can read text from slides and notes pages. No equivalent in localwriter.

### get_presentation_info
- **Status**: MISSING
- **Implementation notes**: mcp-libre returns slide count, dimensions, master pages. No equivalent in localwriter.

---

## Diagnostics / Protection Tools

### document_health_check
- **Status**: MISSING
- **Implementation notes**: mcp-libre runs diagnostics: empty headings, broken bookmarks, orphan images, heading level skips, large unstructured sections. No equivalent in localwriter.

### set_document_protection
- **Status**: MISSING
- **Implementation notes**: mcp-libre can lock/unlock the document for human editing (UI read-only toggle). No equivalent in localwriter.

---

## Tools NEW in localwriter (not in mcp-libre)

### get_document_content
- **New tool**: Exports document as formatted content with scope options (full, selection, range). Character-offset-based approach. Not present in mcp-libre which uses paragraph-based reading.

### apply_document_content
- **New tool**: Insert or replace content with multiple targeting strategies (full, range, search, beginning, end, selection). Supports Markdown/HTML input. Partially replaces mcp-libre's `replace_in_document` and `set_paragraph_text` via search-based targeting.

### find_text
- **New tool**: Character-offset-based text search. Returns `{start, end, text}` per match. Complements `apply_document_content` for range-based edits.

### get_document_outline
- **New tool**: Returns heading hierarchy by path navigation (e.g. "1.2"). Different from `get_document_tree` which uses bookmarks. Simpler path-based approach.

### get_heading_content
- **New tool**: Returns paragraphs under a heading identified by path (e.g. "2.3"). Complements `get_document_outline`.

### get_document_stats
- **New tool**: Returns character count, word count, paragraph count, page count, heading count. Partially replaces `get_paragraph_count` and `get_page_count`.

### get_document_info
- **New tool**: Generic metadata (doc_type, file_url, is_modified, is_new, title, author). Not in mcp-libre as a combined view.

### export_pdf
- **New tool**: Exports document as PDF. Supports writer, calc, draw, impress. Not in mcp-libre.

### generate_image
- **New tool**: AI image generation and insertion. Uses image service backend. Not in mcp-libre.

### edit_image
- **New tool**: AI img2img editing of selected image. Not in mcp-libre.

### cleanup_bookmarks
- **New tool**: Removes all `_mcp_*` bookmarks. Not in mcp-libre.

### Calc-only new tools
- `set_cell_style` -- Apply formatting (bold, colors, alignment, borders, number format) to cell ranges
- `merge_cells` -- Merge cell ranges
- `clear_range` -- Clear contents in a range
- `sort_range` -- Sort a range by column
- `import_csv_from_string` -- Import CSV data
- `delete_structure` -- Delete rows or columns
- `switch_sheet` -- Switch active sheet
- `create_sheet` -- Create new sheet
- `create_chart` -- Create charts from data
- `get_sheet_summary` -- Richer sheet analysis (replaces get_sheet_info)

---

## Cross-cutting Pattern: `file_path` Parameter

The most systematic difference is that **mcp-libre supports a `file_path` parameter on nearly every tool** to operate on any open document, while **localwriter always operates on the active document** and has no `file_path` parameter. This means mcp-libre can work with multiple documents simultaneously, while localwriter is limited to the currently active one.

## Cross-cutting Pattern: Response Format

- mcp-libre returns `{"success": true/false, ...}`
- localwriter returns `{"status": "ok"/"error", ...}`

## Cross-cutting Pattern: Locator System

mcp-libre has a more mature unified locator system (`paragraph:N`, `bookmark:_mcp_xxx`, `heading_text:Title`, `page:N`, `section:Name`) that is supported across most tools. localwriter has locator support only in the writer_nav module tools (get_document_tree, get_heading_children, navigate_heading, get_surroundings, get_page_objects, add_ai_summary, remove_ai_summary). Core writer tools like `insert_at_paragraph`, `read_paragraphs`, and comments tools do NOT support locators.

---

## Priority Porting List (tools most impactful to port)

1. **set_paragraph_text** -- Essential for document editing, returns batch variables
2. **delete_paragraph** -- Essential for document editing
3. **set_paragraph_style** -- Essential for formatting
4. **insert_paragraphs_batch** -- Efficient bulk insertion
5. **search_in_document** -- Paragraph-context search (LO native)
6. **replace_in_document** -- Dedicated find-replace with regex
7. **create_table** -- Table creation
8. **list_images / get_image_info / insert_image / delete_image** -- Complete image management
9. **resolve_comment / scan_tasks** -- Workflow support
10. **create_document / open_document / close_document** -- Document lifecycle
