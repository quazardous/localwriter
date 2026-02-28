# AGENTS.md — Quickstart cheatsheet for AI agents

> [!IMPORTANT]
> Update this file after making nontrivial changes.

## Project

**LocalWriter** — LibreOffice extension (Python/UNO) adding AI editing to Writer, Calc, Draw via chatbot sidebar + MCP server.

- Extend Selection (Ctrl+Q) / Edit Selection (Ctrl+E)
- Chat with Document: sidebar (Writer/Calc/Draw) + menu fallback; tool-calling per doc type
- Settings (endpoint, model, API key, MCP, image options); optional MCP server (localhost)
- Calc `=PROMPT()`; image generation/editing tools (where present)

## Where is what

```
plugin/main.py              Entry point, bootstrap
plugin/version.py           Version (single source of truth)
plugin/plugin.yaml          Global config schema
plugin/_manifest.py         Generated — do not edit
plugin/framework/           Core engine (services, tools, events, config, http, dialogs)
plugin/modules/<name>/      Feature modules (module.yaml + __init__.py + tools + services/ + providers/)
extension/                  Static LO files (XCU, manifest, assets)
scripts/                    Build & deploy scripts
tests/                      Pytest suite (tests/legacy/ = old, may not pass)
Makefile                    All build/dev targets
install.ps1 / install.sh    Dev environment setup (installs bash, make, pyyaml, vendor deps)
```

## Setup & dev loop

```bash
./install.ps1               # Windows: installs deps (bash, make, pyyaml, vendor)
./install.sh                # Linux/macOS equivalent
make build                  # Build .oxt
make deploy                 # Build + reinstall + restart LO + show log
make log                    # Show ~/localwriter.log
make test                   # Pytest
make set-config             # List all config keys
make help                   # All targets
```

## Release

```bash
# bump version in plugin/version.py + CHANGELOG.md, then:
git add -A && git commit -m "v1.x.y: description"
git push
make build
gh release create v1.x.y --target framework --title "v1.x.y" --notes "changelog"
gh release upload v1.x.y build/localwriter.oxt
```

## Build pipeline

```
module.yaml -> generate_manifest.py -> _manifest.py + XCS/XCU + XDL
extension/ + plugin/ + vendor/ -> build_oxt.py -> .oxt
```

## Module structure

Each module in `plugin/modules/<name>/`:
- `module.yaml` — deps, config schema, actions, menus
- `__init__.py` — extends `ModuleBase`
- `tool_*.py` / `tools/` — extends `ToolBase` (auto-discovered)
- `service_*.py` / `services/` — extends `ServiceBase` (explicit or auto-discovered)

Auto-discovered at build time by `generate_manifest.py`.

## Critical rules

- **UNO context**: NEVER store `ctx` from `initialize()`. Use `get_ctx()` from `framework/uno_context.py`.
- **Config**: Namespaced `"module.key"`, access via `ModuleConfigProxy`. Override: `LOCALWRITER_SET_CONFIG="key=val,..."`. Store API keys in config only; no env var fallbacks in production.
- **Document scoping**: `self.xFrame.getController().getModel()` — never `desktop.getCurrentComponent()`.
- **Sidebar**: Panels use programmatic layout (`plugin/framework/panel_layout.py`), not XDL. Use `create_panel_window()` + `add_control()` for new panels.
- **Writer drawing layer**: `hasattr(model, "getDrawPages")` is True for Writer. Use `supportsService()`.
- **DialogProvider**: Use package URL from `PackageInformationProvider.getPackageLocation()` (see `plugin/framework/dialogs.py`). Do not use Basic library script URL — can deadlock with sidebar UNO components.
- **Context**: Use `get_ctx()` from `framework/uno_context.py`; do not use `uno.getComponentContext()` for extension singletons.
- **Multi-document**: Each panel must use `self.xFrame.getController().getModel()` for the document; never rely on "current" component when multiple docs are open.
- **Streaming**: Use worker + queue + main-thread drain with `toolkit.processEventsToIdle()`; do not use UNO Timer for stream draining in sidebar context. Wrap `processEvents`/`processEventsToIdle` in try/except where used (can raise in headless/test). Reuse/cache HTTP client for keep-alive across requests.
- **Optional controls**: When wiring controls that may be missing (e.g. backward compat), use a safe getter and for checkboxes use get/set checkbox helpers if present in the codebase.
- **Format preservation**: Plain-text search replacement uses format-preserving path; content with markup uses import path. Run markup detection on **raw** input before any HTML wrapping; use raw content for the format-preserving path (see `plugin/modules/writer/format_support.py`).
- **MCP server**: MCP HTTP server and main-thread drain are started from `main.py` only (not sidebar). Document targeting via `X-Document-URL` header.

## LibreOffice dialogs (XDL)

- **Units**: Map AppFont units (device- and HiDPI-independent). No raw pixels for layout.
- **Layout**: No flexbox/auto-size; every control needs explicit position/size. Prefer tabs or compact content over scrollbars.
- **Loading**: XDL via DialogProvider with package URL (see `plugin/framework/dialogs.py`). Base URL from `PackageInformationProvider.getPackageLocation(EXTENSION_ID)`.
- **Multi-page (tabs)**: Do not use `dlg:tabpagecontainer` / `dlg:tabpage` (not in XDL DTD). Use `dlg:page` on controls and `dlg.getModel().Step = pageNum` to switch. Set `dlg:page="1"` on root `<dlg:window>` for initial page. Tab buttons: listener must implement `XActionListener` (and `unohelper.Base` if needed).
- **XDL structure**: Root `<dlg:window>` with `dlg:id`, `dlg:width`, `dlg:height`, `dlg:title`; content in `<dlg:bulletinboard>`; controls (`dlg:text`, `dlg:textfield`, `dlg:button`, `dlg:combobox`, `dlg:fixedline`) with `dlg:id`, `dlg:left`, `dlg:top`, `dlg:width`, `dlg:height`.
- **Populate/read**: `dlg.getControl("id").getModel().Text = value` to set; read same property after `dlg.execute()`.
- **Compact layout**: Label height ~10, textfield ~14, gap between rows ~2, margins ~8.
- **Settings dialog**: Control IDs in XDL must match the field list used when populating/reading (single source of truth).
- **Tab listener**: Wire tab buttons with a listener that implements `XActionListener` (and `unohelper.Base`). Example: `class TabListener(unohelper.Base, XActionListener): ... def actionPerformed(self, ev): self._dlg.getModel().Step = self._page`

## Chat sidebar (behavior)

- **Send/Stop lifecycle**: Send disabled at start of actionPerformed, re-enabled only in `finally` when the send completes; prevents concurrent requests. Use per-control try/except when setting button state so one UNO failure cannot leave Send stuck disabled.
- **Document context**: Rebuilt and **replaced** (not appended) on each user message so the context block does not duplicate.
- **Undo**: AI edits during a tool-calling round are grouped into a single undo ("AI Edit"); one Ctrl+Z reverts the whole turn.
- **Doc-type verification**: Re-verify document type in the send path; if it changed since the panel opened (e.g. user switched document), refuse to send and log so the AI never gets the wrong tools.

## Writer navigation and caching

- **Cache**: Document metadata (length, paragraph ranges, page resolution) is cached per document; invalidate on any document-mutating tool (apply content, style, comments, etc.). See `plugin/modules/core/services/document.py` and writer modules.
- **Outline/headings**: `build_heading_tree`, `ensure_heading_bookmarks`, `resolve_locator`; tools: `get_document_outline`, `get_heading_content`, `read_paragraphs`, `insert_at_paragraph`.

## Cross-renderer testing

Sidebar panels use programmatic layout (no XDL) — test on multiple VCL backends to catch rendering issues:

```bash
SAL_USE_VCLPLUGIN=kf6 make deploy      # KDE/Qt6 (install: dnf install libreoffice-kf6)
SAL_USE_VCLPLUGIN=gtk3 make deploy     # GNOME (default)
SAL_USE_VCLPLUGIN=gtk4 make deploy     # GTK4
SAL_USE_VCLPLUGIN=gen make deploy      # X11 pure
```

Check: sidebar controls visible and non-overlapping, resize works, settings dropdowns functional. If the backend is missing, LO silently falls back to default — verify visually.

## Cross-renderer testing

Sidebar panels use programmatic layout (no XDL) — test on multiple VCL backends to catch rendering issues:

```bash
SAL_USE_VCLPLUGIN=kf6 make deploy      # KDE/Qt6 (install: dnf install libreoffice-kf6)
SAL_USE_VCLPLUGIN=gtk3 make deploy     # GNOME (default)
SAL_USE_VCLPLUGIN=gtk4 make deploy     # GTK4
SAL_USE_VCLPLUGIN=gen make deploy      # X11 pure
```

Check: sidebar controls visible and non-overlapping, resize works, settings dropdowns functional. If the backend is missing, LO silently falls back to default — verify visually.

## Debugging

- `~/localwriter.log` — plugin log (overwritten each session)
- `~/soffice-debug.log` — LO internal errors
- Symlinks exist in the project root (`./localwriter.log`, `./soffice-debug.log`) for convenience
- Empty log = `main.py` never loaded = extension not installed
- `make check-ext` — verify install + manifest
- **Legacy debug/agent logs**: If `init_logging(ctx)` and `debug_log` / `agent_log` are used, paths live in LO user config dir or fallback `~/localwriter_debug.log`, `~/localwriter_agent.log`. Agent log only when `enable_agent_log` is true.
- **Finding logs**: Version-dependent LO paths (e.g. `~/.config/libreoffice/4/user/` vs `24/user/`); fallbacks in `plugin/framework/logging.py`.
- **Image generation**: For image-tool errors, check debug/agent log (e.g. tool result snippets in agent log when enabled).

## Config

- Config lives in LO registry (XCS/XCU schema), not a single JSON file. Keys are namespaced per module.

## References

- LibreOffice DevGuide: [Graphical User Interfaces](https://wiki.documentfoundation.org/Documentation/DevGuide/Graphical_User_Interfaces)
- XDL DTD: `xmlscript/dtd/dialog.dtd` (in LibreOffice source)
- Example XDL: `odk/examples/DevelopersGuide/Extensions/DialogWithHelp/DialogWithHelp/Dialog1.xdl`
