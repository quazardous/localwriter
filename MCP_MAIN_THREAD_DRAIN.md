# MCP Main-Thread Drain: Issue and Implementation

This document describes the problem of draining the MCP queue on LibreOffice’s main thread, what was tried, and the current implementation. It is intended for future work and for agents reading the codebase.

---

## 1. The issue

The MCP HTTP server (port 8765) receives requests in a **background thread**. The actual work (resolving the document, reading/writing content, calling UNO) must run on **LibreOffice’s main thread**. So we:

- Enqueue work from the HTTP handler with `execute_on_main_thread(func, ...)` in `core/mcp_thread.py`.
- Must call `drain_mcp_queue()` **on the main thread** periodically so that enqueued work runs and the HTTP request can complete.

If the queue is never drained, every request that needs UNO (e.g. `GET /documents`, `POST /tools/get_document_content`) blocks in `execute_on_main_thread` until the timeout (e.g. 30s) and returns `{"status": "error", "message": "timeout"}`.

**Ideal solution:** A UNO Timer that fires every 100ms on the main thread and calls `drain_mcp_queue()`. That would service MCP at all times without user interaction.

---

## 2. Why the UNO Timer fails

We try to start the timer in `main.py` via `_start_mcp_timer(ctx)` (and from the sidebar via `try_ensure_mcp_timer(ctx)`). The implementation uses:

- `from com.sun.star.util import XTimerListener`
- A class that inherits from `unohelper.Base` and `XTimerListener`
- `timer.addTimerListener(listener)`

**Observed failure:** In the environment where the extension runs, this fails with one of:

- `No module named 'com'`
- `Type com.sun.star.util.XTimerListener is unknown`

**Diagnosis (from earlier instrumentation):**

- `sys.executable` is **system Python** (e.g. `/usr/bin/python3`), not a LibreOffice-embedded interpreter.
- The pyuno bridge does not inject the `com` package into `sys.modules` in this context (or the typelib does not expose `XTimerListener` to this Python).
- Other UNO calls in the project work because they use **string names** and **ctx** (e.g. `createInstanceWithContext("com.sun.star.util.Timer", ctx)`), and never import `com` or inherit from a `com.sun.star` interface. Only the Timer **listener** requires a Python type (`XTimerListener`) for the bridge to wrap the object.

So: the Timer service can be created with string names; the **listener** we pass to `addTimerListener` must implement the UNO interface, and that step fails because we cannot obtain or use the `XTimerListener` type in this Python context.

---

## 3. What we tried

### 3.1 Start Timer from main (dispatch) and from sidebar

- **From main:** When the user enables MCP via Settings or Toggle, we call `_start_mcp_timer(ctx)`. It fails with “No module named 'com'” (dispatch runs under system Python).
- **From sidebar:** When the chat panel is created we call `try_ensure_mcp_timer(self.ctx)` so the timer starts in the “sidebar context.” It still fails with the same error; logs show `sys.executable=/usr/bin/python3`, so the sidebar code path also runs in a context where `com` is not available (or the type is unknown).

### 3.2 Avoid importing `com`: `uno.getTypeByName` + plain class

We tried not importing `com` at all:

- Use `uno.getTypeByName("com.sun.star.util.XTimerListener")` (implemented in the pyuno C extension, does not require the Python `com` module).
- Define a **plain class** (no inheritance from `com` or `unohelper`) that implements `getTypes()` (returning that type), `getImplementationId()`, `notifyTimer()`, and `disposing()` so the pyuno bridge can wrap it.

**Result:** In this environment `uno.getTypeByName("com.sun.star.util.XTimerListener")` raises **“Type com.sun.star.util.XTimerListener is unknown”** (typelib does not provide that type to this Python). So we cannot build a listener without the `com` package or a working `getTypeByName` for that interface.

### 3.3 Drain on user interaction (removed)

We briefly had a workaround: call `drain_mcp_queue()` when the user clicked Send or Clear, or when the panel opened. So MCP requests would complete only after the user interacted with the sidebar. This was removed as an “ugly hack”; the goal is to service MCP without requiring a click.

### 3.4 Drain in the stream drain loop (current)

The chat panel already runs a **main-thread loop** when the user clicks Send: `run_stream_drain_loop()` in `core/async_stream.py` does `q.get(timeout=0.1)`, processes stream items, and calls `toolkit.processEventsToIdle()`. We added:

- An optional `ctx` argument to `run_stream_drain_loop`.
- At the start of each loop iteration, if `ctx` is set and config has `mcp_enabled`, call `drain_mcp_queue()` (in try/except so stream handling is unaffected).

**Result:** MCP is drained **while the user is waiting for the LLM** (streaming). When the user is not streaming, this loop is not running, so MCP requests can still time out unless some other path drains.

### 3.5 Drain in sidebar layout callbacks (current)

We cannot run a dedicated “at all times” loop on the main thread without blocking panel creation (we’d have to start it from the main thread and the only way to start it without blocking would be to schedule it, e.g. with a Timer). So we drain on **every main-thread entry point** the sidebar gives us:

- **`_drain_mcp_if_enabled(ctx)`** in `chat_panel.py`: if `ctx` and config `mcp_enabled`, calls `drain_mcp_queue()` once.
- **`ChatToolPanel.getHeightForWidth`** and **`ChatToolPanel.getMinimalWidth`** call `_drain_mcp_if_enabled(self.ctx)` so whenever the sidebar framework does layout (resize, tab switch, etc.), we drain once.

**Result:** MCP is serviced when the panel is visible and the framework recalculates layout. Frequency depends on how often the sidebar calls these methods; it is not a fixed 100ms tick.

### 3.6 Server start from sidebar; “address already in use”

After a restart, the config may have `mcp_enabled` true but the server was never started in this session (it is only started when the user saves Settings or uses Toggle, or when the sidebar runs `try_ensure_mcp_timer` and calls `_start_mcp_server`). We made the sidebar start the server when the panel is created if config is enabled and the server is not running. That can lead to the server running in the “sidebar process” while the menu (dispatch) runs in another context; the menu’s `_mcp_server` may be `None`, so Status showed STOPPED and Toggle tried to start a second server and got “Address already in use.” We fixed that by:

- Probing the port when Status is shown; if the health check succeeds, we show RUNNING even when we don’t have a handle.
- When starting the server fails with “Address already in use,” we probe health; if it’s our server, we show a message and do not treat it as a fatal error.

---

## 4. Current implementation summary

| Mechanism | When it runs | File / location |
|-----------|----------------|------------------|
| **Timer** | Intended: every 100ms. **In practice: fails** (no `com` / type unknown). | `main._start_mcp_timer`, `main.try_ensure_mcp_timer`; called from sidebar `_wireControls`. |
| **Stream drain loop** | While user has clicked Send and the stream loop is active. | `core/async_stream.run_stream_drain_loop`: each iteration, if `ctx` and `mcp_enabled`, calls `drain_mcp_queue()`. `chat_panel` passes `ctx=self.ctx` into both call sites. |
| **Layout callbacks** | When the sidebar calls `getHeightForWidth` or `getMinimalWidth` on the panel. | `chat_panel.ChatToolPanel.getHeightForWidth`, `getMinimalWidth` → `_drain_mcp_if_enabled(self.ctx)`. |

So at the moment:

- **During streaming:** MCP is drained every ~0.1s (stream loop).
- **When sidebar is open but not streaming:** MCP is drained only when the framework does layout (layout callbacks). There is no true “at all times” loop.

---

## 5. Gaps and possible next steps

1. **Timer still attempted and logged as failed**  
   We still call `_start_mcp_timer` from the sidebar and log “MCP timer failed to start: …” and “MCP timer failure sys.executable=…”. That is intentional so that if the environment ever provides `com` or a working `getTypeByName`, the timer would start without code changes. The failure is non-fatal; we rely on stream + layout drains.

2. **No fixed-interval drain when idle**  
   Without a working Timer (or another way to “schedule work on the main thread” without user action), we cannot run a loop that drains every 100ms when the user is not streaming. Options that were considered but not pursued further:
   - **Idle listener:** If UNO exposes an “idle” callback (e.g. XIdleRunner / addIdleListener) that we could register using only string names and a plain class (no `com`), we could drain on idle. Not verified in the codebase or IDL.
   - **Different Python/typelib for the extension:** Ensure the extension runs in a context where the pyuno bridge injects `com` or where `getTypeByName("com.sun.star.util.XTimerListener")` succeeds. That would be an environment/build/registration change, not a small code change.

3. **Layout callback frequency**  
   If the sidebar rarely calls `getHeightForWidth` / `getMinimalWidth`, MCP requests may still time out when the user is not streaming. Testing and/or profiling would show how often these run; if needed, we could look for other main-thread entry points (e.g. focus or paint listeners) that might be called more often, bearing in mind that adding listeners may again require implementing UNO interfaces (and thus possibly `com` or a working typelib).

4. **Documentation for readers**  
   The code comments in `main.py` (MCP globals, `_start_mcp_timer`), `core/async_stream.py` (MCP drain in stream loop), and `chat_panel.py` (`_drain_mcp_if_enabled`, layout callbacks) explain why the Timer is used, why it fails, and why we drain in the stream loop and in layout callbacks. This file is the single place that summarizes the full story and the things we tried.

---

## 6. References

- **Queue and executor:** `core/mcp_thread.py` — `execute_on_main_thread`, `drain_mcp_queue`, `_mcp_queue`.
- **Timer (attempted):** `main.py` — `_start_mcp_timer`, `try_ensure_mcp_timer`, `_stop_mcp_timer`; MCP globals and comments.
- **Stream loop drain:** `core/async_stream.py` — `run_stream_drain_loop` (optional `ctx`, MCP drain at top of loop).
- **Layout callback drain:** `chat_panel.py` — `_drain_mcp_if_enabled`, `ChatToolPanel.getHeightForWidth`, `ChatToolPanel.getMinimalWidth`.
- **Server start from sidebar:** `main.try_ensure_mcp_timer` starts the server if config is enabled and server not running; `_start_mcp_server` handles “address already in use” when our server is already bound.
- **Logs:** `localwriter_debug.log` (see AGENTS.md §5b); look for `[MCP]` for timer start/failure and queue drain messages.
