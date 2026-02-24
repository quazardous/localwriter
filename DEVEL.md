# LocalWriter — Developer Guide

> **Always use `make` targets** to build, install, kill, restart, and inspect.

## Quick Reference

```bash
make install-force        # First time: build + install (kills LO)
make cycle                # Build + unopkg reinstall + restart LO + show log
make log                  # Show plugin log
make lo-log               # Show LO debug log
make check-ext            # Verify extension + manifest
```

## Project Layout

```
localwriter/
├── extension/              # Static LO extension files (XCU, manifest, dialogs, assets)
├── plugin/
│   ├── main.py             # Entry point — UNO registration + bootstrap
│   ├── plugin.yaml         # Global (main module) config schema
│   ├── version.py          # Single source of truth for version
│   ├── options_handler.py  # LO Options dialog handler
│   ├── _manifest.py        # Generated — module registry (do not edit)
│   ├── framework/          # Core framework (service registry, event bus, tools, HTTP, logging…)
│   ├── lib/                # Bundled libraries (vendored + internal, see below)
│   └── modules/            # Feature modules (see Module System below)
├── scripts/                # Build & dev scripts (build_oxt.py, generate_manifest.py…)
├── tests/                  # Pytest suite
├── vendor/                 # pip-installed vendored deps (gitignored, populated by `make vendor`)
├── requirements-vendor.txt # Vendored pip dependencies
├── pyproject.toml          # Project metadata + dev deps
└── Makefile                # All build/dev/install targets
```

## Module System

Each module lives in `plugin/modules/<name>/` with a `module.yaml` manifest declaring its name, dependencies, provided services, and config schema. Modules are auto-discovered at build time.

```yaml
# Example: plugin/modules/mcp/module.yaml
name: mcp
description: MCP JSON-RPC server for external tool access
requires: [document, config, events, http_routes]
config:
  port:
    type: int
    default: 8766
```

`generate_manifest.py` reads all `module.yaml` files and produces:
- `plugin/_manifest.py` — module registry used at runtime
- XCS/XCU pairs — LO registry schemas for each module's config
- XDL dialog pages — auto-generated Options UI per module
- `OptionsDialog.xcu` — registers dialog pages in LO

Current modules: `core`, `writer`, `writer.nav`, `writer.index`, `calc`, `draw`, `common`, `batch`, `openai_compat`, `ollama`, `horde`, `chatbot`, `http`, `mcp`, `tunnel`, `tunnel.bore`, `tunnel.cloudflare`, `tunnel.ngrok`, `tunnel.tailscale`.

## Development Cycle

```bash
# Edit code, then:
make cycle                # Full rebuild + reinstall + restart + verify

# With config overrides:
make cycle LOCALWRITER_SET_CONFIG="mcp.port=9000,mcp.host=0.0.0.0"
```

The `cycle` target does: vendor deps → generate manifest + XCS/XCU → assemble `build/bundle/` → zip .oxt → kill LO → `unopkg remove` + `unopkg add` → start LO → show log.

> **Note:** `make cycle` returns once LO is launched — it does **not** wait for LO to exit. The log output at the end is a quick snapshot; use `make log` or `make log-tail` for the full output.

## Build Pipeline

```
requirements-vendor.txt → uv pip install --target vendor/
                                                    ↓
module.yaml → generate_manifest.py → _manifest.py + XCS/XCU + XDL + OptionsDialog.xcu
                                                    ↓
extension/ + plugin/ + vendor/ + build/generated/ → build_oxt.py → build/bundle/ → .oxt
```

`make build` runs `make vendor` (installs pip deps into `vendor/`), generates manifests, assembles everything into `build/bundle/` (copying vendored packages into `plugin/lib/`), then zips it into `.oxt`.

### Vendored Dependencies

Third-party pip packages are listed in `requirements-vendor.txt` and installed into `vendor/` (gitignored). During build, `build_oxt.py` copies top-level packages from `vendor/` into `build/bundle/plugin/lib/`, skipping `.dist-info` metadata. This keeps the .oxt self-contained without committing third-party code to git.

```bash
make vendor               # Install vendored deps into vendor/
```

`plugin/lib/` also contains internal libraries (`aihordeclient`, `translation.py`, `default_models.py`) that are project code, not pip packages — these are tracked in git normally.

### Tweaking the bundle

After `make build`, `build/bundle/` contains the full extension content. You can edit files there (XDL dialogs, XCS/XCU, Python code...) and re-zip without regenerating:

```bash
make build                          # Full build → creates build/bundle/
# Edit something in build/bundle/
vim build/bundle/dialogs/mcp.xdl
make repack-cycle                   # Re-zip bundle + reinstall + restart LO
```

This is useful for quick iteration on generated files (dialogs, registry schemas) without going through the full generate step.

| Target | What |
|--------|------|
| `make repack` | Re-zip `build/bundle/` → .oxt (no regeneration) |
| `make repack-cycle` | Repack + reinstall + restart LO + show log |

## Config Overrides

Override config values persistently via environment variable:

```bash
# Set config keys at LO launch (values are written to LO registry)
make lo-start LOCALWRITER_SET_CONFIG="mcp.port=9000"

# Or during a full cycle
make cycle LOCALWRITER_SET_CONFIG="mcp.port=9000,mcp.host=0.0.0.0"

# Show available config keys and their defaults
make set-config
```

Format: `key=value,key=value,...` — values are coerced to the type declared in the module's `module.yaml` schema (boolean, int, float, string).

## Testing MCP

Once LO is running with MCP enabled:

```bash
# Health check
curl -s http://localhost:8766/health

# MCP initialize
curl -s http://localhost:8766/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# List tools
curl -s http://localhost:8766/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

## Debugging

- `~/localwriter.log` — plugin log, overwritten each LO session, DEBUG level
- `~/soffice-debug.log` — LO internal errors
- If `~/localwriter.log` is empty, `main.py` never loaded
- `make check-ext` — verify extension installed + manifest valid

## Auto-Start Mechanism

The extension auto-starts via two mechanisms:
1. **Jobs.xcu** — `OnStartApp` event triggers `MainJob.execute()` which calls `bootstrap(ctx)`
2. **Fallback thread** — a daemon thread waits 3s then bootstraps if OnStartApp didn't fire

LO launches with `--writer` flag (opens a blank document) to ensure a desktop is available.

## Makefile Targets

| Target | What |
|--------|------|
| **Build** | |
| `make build` | Vendor deps + generate + assemble bundle + zip .oxt |
| `make vendor` | Install vendored pip deps into `vendor/` |
| `make repack` | Re-zip `build/bundle/` only (no regeneration) |
| `make repack-cycle` | Repack + reinstall + restart LO + show log |
| `make manifest` | Regenerate _manifest.py + XCS/XCU |
| `make clean` | Remove build/ and __pycache__ |
| **Install** | |
| `make install-force` | Build + install (no prompts, kills LO) |
| `make uninstall` | Remove extension |
| `make cache` | Hot-deploy to LO cache |
| `make cycle` | Build + unopkg reinstall + restart + show log |
| **LibreOffice** | |
| `make lo-start` | Launch LO with debug logging |
| `make lo-kill` | Kill LO |
| `make lo-restart` | Kill + start |
| **Config** | |
| `make set-config` | Show available config keys + usage |
| **Logs** | |
| `make log` | Show plugin log |
| `make log-tail` | Tail plugin log |
| `make lo-log` | Show LO debug log |
| **Cache** | |
| `make clean-cache` | Fix revoked flags, stale locks |
| `make nuke-cache-force` | Wipe extension cache (no prompts) |
| **Test** | |
| `make test` | Run pytest |
| `make check-ext` | Verify extension + manifest |

## POC Extension (`poc-ext/`)

A standalone throwaway extension used for **testing LO features in isolation** (options dialogs, registry persistence, UNO APIs, etc.). It always uses the same extension ID (`org.extension.poc`) so it can be swapped out with different content without cleanup issues.

```bash
make poc-cycle         # Build + install + restart LO + show log
make poc-log           # Show POC log (~/.poc-ext.log)
make poc-log-tail      # Tail POC log
make poc-uninstall     # Remove POC extension
```

The `poc-ext/` directory is gitignored. Change its contents freely to test different things — the extension ID and Makefile targets stay the same.

## Version

Single source of truth: `plugin/version.py`. Propagated at build time to `description.xml` and `pyproject.toml`.
