"""HTTP server module — owns the HTTP server lifecycle."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.http")


class HttpModule(ModuleBase):
    """Manages the shared HTTP server and route registry.

    Other modules (MCP, chatbot, debug) register routes via the
    ``http_routes`` service during their initialize() phase.
    This module starts the server in start_background() (phase 2b).
    """

    def initialize(self, services):
        from plugin.framework.http_routes import HttpRouteRegistry

        self._registry = HttpRouteRegistry()
        services.register_instance("http_routes", self._registry)
        self._server = None
        self._services = services

        # Built-in endpoints
        self._registry.add("GET", "/health", self._handle_health)
        self._registry.add("GET", "/", self._handle_info)

        if hasattr(services, "events"):
            services.events.subscribe("config:changed", self._on_config_changed)

    def start_background(self, services):
        if services.config.proxy_for(self.name).get("enabled"):
            self._start_server(services)

    def _on_config_changed(self, **data):
        key = data.get("key", "")
        if not key.startswith("http."):
            return
        cfg = self._services.config.proxy_for(self.name)
        enabled = cfg.get("enabled")
        if enabled and not self._server:
            self._start_server(self._services)
        elif not enabled and self._server:
            self._stop_server()

    def _start_server(self, services):
        from plugin.framework.http_server import HttpServer

        cfg = services.config.proxy_for(self.name)
        event_bus = getattr(services, "events", None)

        self._server = HttpServer(
            route_registry=self._registry,
            port=cfg.get("port") or 8766,
            host=cfg.get("host") or "localhost",
            use_ssl=cfg.get("use_ssl") or False,
            ssl_cert=cfg.get("ssl_cert") or "",
            ssl_key=cfg.get("ssl_key") or "",
        )
        try:
            self._server.start()
            if event_bus:
                status = self._server.get_status()
                event_bus.emit("http:server_started",
                               port=status["port"], host=status["host"],
                               url=status["url"])
        except Exception:
            log.exception("Failed to start HTTP server")
            self._server = None

    def _stop_server(self):
        if self._server:
            self._server.stop()
            self._server = None
            event_bus = getattr(self._services, "events", None)
            if event_bus:
                event_bus.emit("http:server_stopped", reason="shutdown")

    def shutdown(self):
        self._stop_server()

    # ---- Built-in route handlers ----

    def _handle_health(self, body, headers, query):
        from plugin.version import EXTENSION_VERSION
        return (200, {
            "status": "healthy",
            "server": "LocalWriter",
            "version": EXTENSION_VERSION,
        })

    def _handle_info(self, body, headers, query):
        from plugin.version import EXTENSION_VERSION
        routes = self._registry.list_routes()
        return (200, {
            "name": "LocalWriter",
            "version": EXTENSION_VERSION,
            "description": "LocalWriter HTTP server",
            "routes": ["%s %s" % (m, p) for m, p in sorted(routes)],
        })
