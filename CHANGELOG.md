# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — framework branch (WIP)

> The master port is not yet complete.

### Added

- Modular plugin framework with service registry, tool registry, event bus, and YAML-based module manifests
- 39 tools ported from mcp-libre (editing, search, images, frames, workflow, lifecycle, impress, diagnostics)
- HTTP server, tunnel, batch, writer navigation, and writer index modules

### Changed

- Architecture: flat `core/` monolith → modular `plugin/framework/` + `plugin/modules/`
- Config: `localwriter.json` → per-module YAML schemas with LibreOffice native Options panel
- Build: `build.sh` → `Makefile` + Python scripts (cross-platform)

### Removed

- `core/` directory, root-level `main.py`/`chat_panel.py`, custom settings dialogs
- `localwriter.json.example`, `build.sh`, root `META-INF/`
- `pricing.py`, `eval_runner.py` (not yet ported)

### Fixed

- UNO context going stale — now uses fresh `get_ctx()` on every call
- `search_in_document` regex compilation and result counting
- `set_image_properties` crop parameter handling
