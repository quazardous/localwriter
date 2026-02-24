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

## Development Cycle

```bash
# Edit code, then:
make cycle                # Full rebuild + reinstall + restart + verify

# With config overrides:
make cycle LOCALWRITER_SET_CONFIG="mcp.port=9000,mcp.host=0.0.0.0"
```

The `cycle` target does: build .oxt → kill LO → clean locks → `unopkg remove` + `unopkg add` → start LO → wait → show log.

## Config Overrides

Override config values persistently via environment variable:

```bash
# Set config keys at LO launch (values are persisted to localwriter.json)
make lo-start LOCALWRITER_SET_CONFIG="mcp.port=9000"

# Or during a full cycle
make cycle LOCALWRITER_SET_CONFIG="mcp.port=9000,mcp.host=0.0.0.0"

# Show available config keys and their defaults
make set-config
```

Format: `key=value,key=value,...` — values are coerced to the type declared in the module's `module.yaml` schema (boolean, int, float, string).

This is a **repair mechanism**: overrides are written to `~/.config/localwriter.json` and persist across restarts.

## Testing MCP

Once LO is running with MCP enabled:

```bash
# Health check
curl -s http://localhost:8765/health

# MCP initialize
curl -s http://localhost:8765/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# List tools
curl -s http://localhost:8765/mcp -H 'Content-Type: application/json' \
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
| `make build` | Build .oxt |
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

## Build Pipeline

`module.yaml` -> `generate_manifest.py` -> `_manifest.py` + XCS/XCU + manifest.xml

Then `build_oxt.py` assembles `plugin/` + `extension/` + generated files into `.oxt`.

## Version

Single source of truth: `plugin/version.py`. Propagated at build time to `description.xml` and `pyproject.toml`.
