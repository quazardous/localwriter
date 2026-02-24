"""MCP HTTP server for LocalWriter.

JSON-RPC 2.0 over HTTP implementing the MCP Streamable HTTP spec.
Handles backpressure: one tool execution at a time on the VCL main
thread, with a short wait timeout for queued requests and a longer
processing timeout for active execution.
"""

import json
import logging
import socketserver
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from plugin.modules.mcp.thread import execute_on_main_thread

log = logging.getLogger("localwriter.mcp.server")

# MCP protocol version we advertise
MCP_PROTOCOL_VERSION = "2025-11-25"

# Backpressure — one tool execution at a time
_tool_semaphore = threading.Semaphore(1)
_WAIT_TIMEOUT = 5.0
_PROCESS_TIMEOUT = 60.0


class BusyError(Exception):
    """The VCL main thread is already processing another tool call."""


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in its own thread."""
    daemon_threads = True


# JSON-RPC helpers
def _jsonrpc_ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


# Standard JSON-RPC error codes
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603
_SERVER_BUSY = -32000
_EXECUTION_TIMEOUT = -32001

# Session management
_mcp_session_id = None


class MCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the MCP streamable-http protocol."""

    tool_registry = None
    service_registry = None
    event_bus = None
    version = "unknown"

    # ── GET ──────────────────────────────────────────────────────────

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == "/health":
                self._send_json(200, {
                    "status": "healthy",
                    "server": "LocalWriter MCP",
                    "version": self.version,
                })
            elif path == "/":
                self._send_json(200, self._get_server_info())
            elif path == "/mcp":
                accept = self.headers.get("Accept", "")
                if "text/event-stream" not in accept:
                    self._send_json(406, {
                        "error": "Not Acceptable: must Accept text/event-stream"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self._send_cors_headers()
                self.end_headers()
                try:
                    while True:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        time.sleep(15)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
            elif path == "/sse":
                self._handle_sse_stream()
            else:
                self._send_json(404, {"error": "Not found"})
        except Exception as e:
            log.error("GET %s error: %s", self.path, e)
            self._send_json(500, {"error": str(e)})

    # ── POST ─────────────────────────────────────────────────────────

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path in ("/messages", "/sse"):
                body = self._read_body()
                if body is not None:
                    self._handle_sse_post(body)
                return
            if path == "/mcp":
                body = self._read_body()
                if body is not None:
                    self._handle_mcp(body)
                return
            self._send_json(404, {"error": "Not found"})
        except Exception as e:
            log.error("POST %s error: %s", self.path, e)
            self._send_json(500, {"error": str(e)})

    # ── DELETE ────────────────────────────────────────────────────────

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/mcp":
            self.send_response(200)
            self._send_cors_headers()
            self.end_headers()
        else:
            self._send_json(404, {"error": "Not found"})

    # ── OPTIONS ───────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # ── MCP protocol handler ──────────────────────────────────────────

    def _handle_mcp(self, msg):
        """Route MCP JSON-RPC request(s) — single or batch."""
        global _mcp_session_id

        method = msg.get("method", "?") if isinstance(msg, dict) else "batch"
        req_id = msg.get("id") if isinstance(msg, dict) else None
        log.info("[MCP] <<< %s (id=%s)", method, req_id)

        is_initialize = (isinstance(msg, dict)
                         and msg.get("method") == "initialize")

        # Batch request
        if isinstance(msg, list):
            responses = []
            for item in msg:
                result = self._process_jsonrpc(item)
                if result is not None:
                    _status, response = result
                    responses.append(response)
            if responses:
                self._send_json(200, responses)
            else:
                self.send_response(202)
                self._send_cors_headers()
                self.end_headers()
            return

        # Single request
        result = self._process_jsonrpc(msg)
        if result is None:
            self.send_response(202)
            self._send_cors_headers()
            if _mcp_session_id:
                self.send_header("Mcp-Session-Id", _mcp_session_id)
            self.end_headers()
            return
        status, response = result

        if is_initialize and status == 200:
            _mcp_session_id = str(uuid.uuid4())

        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        if _mcp_session_id:
            self.send_header("Mcp-Session-Id", _mcp_session_id)
        self.end_headers()
        body = json.dumps(response, ensure_ascii=False, default=str)
        log.info("[MCP] >>> %s (id=%s) -> %d", method, req_id, status)
        self.wfile.write(body.encode("utf-8"))

    # ── MCP method handlers ───────────────────────────────────────────

    def _mcp_initialize(self, params):
        client_version = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
        return {
            "protocolVersion": client_version,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "LocalWriter MCP",
                "version": self.version,
            },
            "instructions": (
                "LocalWriter MCP — AI document workspace. "
                "WORKFLOW: 1) Use tools to interact with LibreOffice documents. "
                "2) Tools are filtered by document type (writer/calc/draw). "
                "3) All UNO operations run on the main thread for thread safety."
            ),
        }

    def _mcp_ping(self, params):
        return {}

    def _mcp_tools_list(self, params):
        doc_type = self._detect_active_doc_type()
        schemas = self.tool_registry.get_mcp_schemas(doc_type)
        return {"tools": schemas}

    def _mcp_resources_list(self, params):
        return {"resources": []}

    def _mcp_prompts_list(self, params):
        return {"prompts": []}

    def _mcp_tools_call(self, params):
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not tool_name:
            raise ValueError("Missing 'name' in tools/call params")

        if self.event_bus:
            self.event_bus.emit("mcp:request", tool=tool_name, args=arguments)

        result = self._execute_with_backpressure(tool_name, arguments)

        if self.event_bus:
            snippet = str(result)[:100] if result else ""
            self.event_bus.emit("mcp:result", tool=tool_name,
                                result_snippet=snippet)

        is_error = (isinstance(result, dict)
                    and result.get("status") == "error")
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False,
                                       default=str),
                }
            ],
            "isError": is_error,
        }

    # ── JSON-RPC processing ───────────────────────────────────────────

    def _process_jsonrpc(self, msg):
        """Process a JSON-RPC message.

        Returns (http_status, response_dict) or None for notifications.
        """
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return (400, _jsonrpc_error(
                None, _INVALID_REQUEST, "Invalid JSON-RPC 2.0 request"))

        method = msg.get("method", "")
        params = msg.get("params", {})
        req_id = msg.get("id")

        if req_id is None:
            return None

        handler = {
            "initialize":      self._mcp_initialize,
            "ping":            self._mcp_ping,
            "tools/list":      self._mcp_tools_list,
            "tools/call":      self._mcp_tools_call,
            "resources/list":  self._mcp_resources_list,
            "prompts/list":    self._mcp_prompts_list,
        }.get(method)

        if handler is None:
            return (400, _jsonrpc_error(
                req_id, _METHOD_NOT_FOUND,
                "Unknown method: %s" % method))

        try:
            result = handler(params)
            return (200, _jsonrpc_ok(req_id, result))
        except BusyError as e:
            log.warning("MCP %s: busy (%s)", method, e)
            return (429, _jsonrpc_error(
                req_id, _SERVER_BUSY, str(e),
                {"retryable": True}))
        except TimeoutError as e:
            log.error("MCP %s: timeout (%s)", method, e)
            return (504, _jsonrpc_error(
                req_id, _EXECUTION_TIMEOUT, str(e)))
        except Exception as e:
            log.error("MCP %s error: %s", method, e, exc_info=True)
            return (500, _jsonrpc_error(
                req_id, _INTERNAL_ERROR, str(e)))

    # ── SSE transport (ChatGPT compatibility) ─────────────────────────

    def _handle_sse_stream(self):
        """GET /sse — notification stream (keepalive only)."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self._send_cors_headers()
            self.end_headers()
            log.info("[SSE] GET stream opened")
            while True:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                time.sleep(15)
        except (BrokenPipeError, ConnectionResetError, OSError):
            log.info("[SSE] GET stream disconnected")

    def _handle_sse_post(self, msg):
        """POST /sse or /messages — streamable HTTP (same as /mcp)."""
        method = msg.get("method", "?") if isinstance(msg, dict) else "batch"
        req_id = msg.get("id") if isinstance(msg, dict) else None
        log.info("[SSE] POST <<< %s (id=%s)", method, req_id)

        result = self._process_jsonrpc(msg)
        if result is None:
            self.send_response(202)
            self._send_cors_headers()
            self.end_headers()
            return

        status, response = result
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps(response, ensure_ascii=False, default=str)
        log.info("[SSE] POST >>> %s (id=%s) -> %d", method, req_id, status)
        self.wfile.write(body.encode("utf-8"))

    # ── Backpressure execution ────────────────────────────────────────

    def _execute_with_backpressure(self, tool_name, arguments):
        """Execute a tool on the VCL main thread with backpressure."""
        acquired = _tool_semaphore.acquire(timeout=_WAIT_TIMEOUT)
        if not acquired:
            raise BusyError(
                "LibreOffice is busy processing another tool call. "
                "Please wait a moment and retry.")
        try:
            return execute_on_main_thread(
                self._execute_tool_on_main, tool_name, arguments,
                timeout=_PROCESS_TIMEOUT)
        finally:
            _tool_semaphore.release()

    def _execute_tool_on_main(self, tool_name, arguments):
        """Execute a tool via the ToolRegistry. Runs on main thread."""
        from plugin.framework.tool_context import ToolContext

        registry = self.tool_registry
        svc_registry = self.service_registry

        # Resolve active document
        doc = None
        doc_type = "writer"
        try:
            doc_svc = svc_registry.document
            doc = doc_svc.get_active_document()
            if doc:
                doc_type = doc_svc.detect_doc_type(doc)
        except Exception:
            pass

        if doc is None:
            return {"status": "error",
                    "message": "No document open in LibreOffice."}

        # Get UNO context
        ctx = None
        try:
            import uno
            ctx = uno.getComponentContext()
        except Exception:
            pass

        context = ToolContext(
            doc=doc,
            ctx=ctx,
            doc_type=doc_type,
            services=svc_registry,
            caller="mcp",
        )

        t0 = time.perf_counter()
        result = registry.execute(tool_name, context, **arguments)
        elapsed = time.perf_counter() - t0

        if isinstance(result, dict):
            result["_elapsed_ms"] = round(elapsed * 1000, 1)

        return result

    # ── Helpers ────────────────────────────────────────────────────────

    def _detect_active_doc_type(self):
        try:
            doc_svc = self.service_registry.document
            doc = doc_svc.get_active_document()
            if doc:
                return doc_svc.detect_doc_type(doc)
        except Exception:
            pass
        return None

    def _get_server_info(self):
        tool_count = len(self.tool_registry.tool_names) if self.tool_registry else 0
        return {
            "name": "LocalWriter MCP",
            "version": self.version,
            "description": "MCP server integrated into LibreOffice",
            "mcp_endpoint": "/mcp",
            "endpoints": {
                "POST /mcp": "MCP streamable-http (JSON-RPC 2.0)",
                "GET /mcp": "MCP streamable-http SSE notifications",
                "GET /sse": "MCP SSE transport (legacy, ChatGPT)",
                "POST /messages": "MCP SSE transport messages",
                "GET /": "Server info",
                "GET /health": "Health check",
            },
            "tools_count": tool_count,
        }

    def _read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Invalid JSON body: %s", raw[:200])
            self._send_json(400, {"error": "Invalid JSON"})
            return None

    def _send_json(self, status, data):
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(
            data, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization, Mcp-Session-Id")
        self.send_header("Access-Control-Expose-Headers",
                         "Mcp-Session-Id")

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.client_address[0], fmt % args)


class MCPServer:
    """MCP HTTP server using the framework's ToolRegistry."""

    def __init__(self, tool_registry, service_registry, event_bus=None,
                 port=8765, host="localhost", use_ssl=True, version="unknown"):
        self.tool_registry = tool_registry
        self.service_registry = service_registry
        self.event_bus = event_bus
        self.port = port
        self.host = host
        self.use_ssl = use_ssl
        self.version = version
        self.server = None
        self.server_thread = None
        self.running = False

    def start(self):
        if self.running:
            log.warning("MCP server is already running")
            return

        MCPRequestHandler.tool_registry = self.tool_registry
        MCPRequestHandler.service_registry = self.service_registry
        MCPRequestHandler.event_bus = self.event_bus
        MCPRequestHandler.version = self.version

        self.server = _ThreadedHTTPServer(
            (self.host, self.port), MCPRequestHandler)

        if self.use_ssl:
            from plugin.modules.mcp.ssl_certs import ensure_certs, create_ssl_context
            cert_path, key_path = ensure_certs()
            ssl_ctx = create_ssl_context(cert_path, key_path)
            self.server.socket = ssl_ctx.wrap_socket(
                self.server.socket, server_side=True)
            log.info("TLS enabled with cert %s", cert_path)

        self.running = True
        self.server_thread = threading.Thread(
            target=self._run, daemon=True, name="mcp-http-server")
        self.server_thread.start()

        scheme = "https" if self.use_ssl else "http"
        url = "%s://%s:%s/mcp" % (scheme, self.host, self.port)
        log.info("MCP server ready — %s (%d tools)",
                 url, len(self.tool_registry.tool_names))

        if self.event_bus:
            self.event_bus.emit("mcp:server_started",
                                port=self.port, host=self.host, url=url)

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            log.info("MCP HTTP server stopped")
        if self.event_bus:
            self.event_bus.emit("mcp:server_stopped", reason="shutdown")

    def _run(self):
        try:
            self.server.serve_forever()
        except Exception as e:
            if self.running:
                log.error("HTTP server error: %s", e)
        finally:
            self.running = False

    def is_running(self):
        return self.running

    def get_status(self):
        scheme = "https" if self.use_ssl else "http"
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "ssl": self.use_ssl,
            "mcp_url": "%s://%s:%s/mcp" % (scheme, self.host, self.port),
            "tools_count": len(self.tool_registry.tool_names),
            "thread_alive": (self.server_thread.is_alive()
                             if self.server_thread else False),
        }
