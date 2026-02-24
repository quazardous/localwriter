"""MCP JSON-RPC server module."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.mcp")


class MCPModule(ModuleBase):
    """Exposes tools via an MCP HTTP server."""

    def initialize(self, services):
        self._services = services
        self._server = None

        # Auto-start if enabled
        if services.config.proxy_for(self.name).get("enabled"):
            self._start_server(services)

        # Listen for config changes to start/stop dynamically
        if hasattr(services, "events"):
            services.events.subscribe("config:changed", self._on_config_changed)

    def _on_config_changed(self, **data):
        key = data.get("key", "")
        if not key.startswith("mcp."):
            return
        cfg = self._services.config.proxy_for(self.name)
        enabled = cfg.get("enabled")
        if enabled and not self._server:
            self._start_server(self._services)
        elif not enabled and self._server:
            self._stop_server()

    def _start_server(self, services):
        from plugin.modules.mcp.server import MCPServer
        from plugin.version import EXTENSION_VERSION

        cfg = services.config.proxy_for(self.name)
        tool_registry = services.tools
        event_bus = getattr(services, "events", None)

        self._server = MCPServer(
            tool_registry=tool_registry,
            service_registry=services,
            event_bus=event_bus,
            port=cfg.get("port") or 8765,
            host=cfg.get("host") or "localhost",
            use_ssl=cfg.get("use_ssl") or False,
            version=EXTENSION_VERSION,
        )
        try:
            self._server.start()
        except Exception:
            log.exception("Failed to start MCP server")
            self._server = None

    def _stop_server(self):
        if self._server:
            self._server.stop()
            self._server = None

    def shutdown(self):
        self._stop_server()
