"""LocalWriter entry point — bootstraps the module framework.

Responsibilities:
1. Resolve module load order from dependency graph (_manifest.py)
2. Initialize core services first, then all other modules
3. Auto-discover tools from each module's tools/ subpackage
4. Register UNO components (MainJob, sidebar panel factory)

All runtime code lives under plugin/. This file is the single entry
point registered in META-INF/manifest.xml.
"""

import logging
import os
import sys
import threading

# ── File logger (debug even when LO console is hidden) ──────────────────────
# Set up on the 'localwriter' logger (not root) so it works regardless of
# root logger state configured by other extensions (e.g. mcp-libre).
# Cannot import from plugin.framework here — sys.path isn't set up yet.

_log_path = os.path.join(os.path.expanduser("~"), "localwriter.log")
_logger = logging.getLogger("localwriter")
_logger.handlers.clear()
_logger.propagate = False
_handler = logging.FileHandler(_log_path, mode="w", encoding="utf-8")
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.DEBUG)

log = logging.getLogger("localwriter.main")

_version = "?"
try:
    _vf = os.path.join(os.path.dirname(__file__), "version.py")
    with open(_vf) as _f:
        for _line in _f:
            if _line.startswith("EXTENSION_VERSION"):
                _version = _line.split("=", 1)[1].strip().strip("\"'")
                break
except Exception:
    pass
log.info("=== LocalWriter %s — main.py loaded ===", _version)

# Extension identifier (matches description.xml)
EXTENSION_ID = "org.extension.localwriter"

# ── Singleton registries ──────────────────────────────────────────────

_services = None
_tools = None
_modules = []
_init_lock = threading.Lock()
_initialized = False


def _ensure_extension_on_path(ctx):
    """Add the extension's install directory to sys.path."""
    try:
        import uno
        pip = ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        ext_url = pip.getPackageLocation(EXTENSION_ID)
        if ext_url.startswith("file://"):
            ext_path = str(uno.fileUrlToSystemPath(ext_url))
        else:
            ext_path = ext_url
        if ext_path and ext_path not in sys.path:
            sys.path.insert(0, ext_path)
    except Exception:
        pass

    # Also ensure plugin/ parent is on path so "plugin.xxx" imports work
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(plugin_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)


def _load_manifest():
    """Load the generated module manifest.

    Returns a list of module descriptors sorted by dependency order.
    Each descriptor is a dict with keys: name, module_class, requires, config, ...
    """
    try:
        from plugin._manifest import MODULES
        return MODULES
    except ImportError:
        log.warning("_manifest.py not found — using fallback discovery")
        return _fallback_discover_modules()


def _fallback_discover_modules():
    """Discover modules by scanning plugin/modules/ for module.yaml files.

    Used when _manifest.py has not been generated (dev mode).
    Requires PyYAML.
    """
    modules_dir = os.path.join(os.path.dirname(__file__), "modules")
    if not os.path.isdir(modules_dir):
        return []

    result = []
    for entry in sorted(os.listdir(modules_dir)):
        yaml_path = os.path.join(modules_dir, entry, "module.yaml")
        if not os.path.isfile(yaml_path):
            continue
        try:
            import yaml
            with open(yaml_path) as f:
                manifest = yaml.safe_load(f)
            manifest.setdefault("name", entry)
            result.append(manifest)
        except Exception:
            log.exception("Failed to load %s", yaml_path)

    return _topo_sort(result)


def _topo_sort(modules):
    """Topological sort of modules by 'requires' dependencies.

    Ensures core is always first. Returns sorted list.
    """
    by_name = {m["name"]: m for m in modules}
    # Services provided by each module
    provides = {}
    for m in modules:
        for svc in m.get("provides_services", []):
            provides[svc] = m["name"]

    visited = set()
    order = []

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        m = by_name.get(name)
        if m is None:
            return
        for req in m.get("requires", []):
            provider = provides.get(req, req)
            if provider in by_name:
                visit(provider)
        order.append(m)

    # core first
    if "core" in by_name:
        visit("core")
    for name in by_name:
        visit(name)

    return order


def _import_module_class(module_manifest):
    """Import and return the ModuleBase subclass for a module."""
    name = module_manifest["name"]
    # Directory convention: dots in name map to underscores
    package = "plugin.modules.%s" % name.replace(".", "_")
    try:
        import importlib
        mod = importlib.import_module(package)
        # Find the ModuleBase subclass
        from plugin.framework.module_base import ModuleBase
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if (isinstance(obj, type) and issubclass(obj, ModuleBase)
                    and obj is not ModuleBase):
                return obj
    except Exception:
        log.exception("Failed to import module: %s", name)
    return None


def get_services():
    """Return the global ServiceRegistry (lazy-init)."""
    global _services
    if _services is None:
        bootstrap()
    return _services


def get_tools():
    """Return the global ToolRegistry (lazy-init)."""
    global _tools
    if _tools is None:
        bootstrap()
    return _tools


def bootstrap(ctx=None):
    """Initialize the entire framework.

    Idempotent — safe to call multiple times.
    """
    global _services, _tools, _modules, _initialized

    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        if ctx:
            _ensure_extension_on_path(ctx)
            # Store fallback ctx for environments where uno module
            # is not importable (shouldn't happen in LO, but safe)
            from plugin.framework.uno_context import set_fallback_ctx
            set_fallback_ctx(ctx)

        from plugin.framework.service_registry import ServiceRegistry
        from plugin.framework.tool_registry import ToolRegistry

        _services = ServiceRegistry()
        _tools = ToolRegistry(_services)

        # Register the tool registry itself as a service
        _services.register_instance("tools", _tools)

        # Load and sort modules
        manifests = _load_manifest()

        manifest_dict = {m["name"]: m for m in manifests}

        # ── Phase 1: initialize modules ──────────────────────────────
        log.info("── Phase 1: initialize ─────────────────────────────")

        for manifest in manifests:
            name = manifest["name"]
            if name == "main":
                continue  # framework-level config, not a loadable module
            cls = _import_module_class(manifest)
            if cls is None:
                log.warning("Skipping module with no class: %s", name)
                continue

            instance = cls()
            instance.name = name

            try:
                instance.initialize(_services)
                log.info("Module initialized: %s", name)
            except Exception:
                log.exception("Failed to initialize module: %s", name)
                continue

            _modules.append(instance)

            # After core registers config service, load all config defaults
            # so subsequent modules can read their config during init
            if name == "core":
                config_svc = _services.get("config")
                if config_svc:
                    config_svc.set_manifest(manifest_dict)
                    log.info("Config defaults loaded for %d modules",
                             len(manifest_dict))
                    # Apply configured log level
                    from plugin.framework.logging import set_log_level
                    level = config_svc.proxy_for("core").get(
                        "log_level", "DEBUG")
                    set_log_level(level)
                    log.info("Log level set to %s", level)

            # Auto-discover tools from this module's tools/ subpackage
            # Directory convention: dots in name map to underscores
            # e.g. "tunnel.bore" -> modules/tunnel_bore/tools
            dir_name = name.replace(".", "_")
            tools_dir = os.path.join(
                os.path.dirname(__file__), "modules", dir_name, "tools")
            if os.path.isdir(tools_dir):
                tools_pkg = "plugin.modules.%s.tools" % dir_name
                _tools.discover(tools_dir, tools_pkg)

        # Wire event bus into config service
        if config_svc:
            events_svc = _services.get("events")
            if events_svc:
                config_svc.set_events(events_svc)

        # Initialize services that need a UNO context
        if ctx:
            _services.initialize_all(ctx)

        log.info("── Phase 1 complete: %d modules initialized ────────",
                 len(_modules))

        # Emit modules:initialized event
        events_svc = _services.get("events")
        if events_svc:
            events_svc.emit("modules:initialized",
                            modules=[m.name for m in _modules])

        # ── Phase 2a: start modules on VCL main thread ────────────────
        log.info("── Phase 2a: start (main thread) ────────────────────")

        from plugin.framework.main_thread import execute_on_main_thread

        for mod in _modules:
            try:
                execute_on_main_thread(mod.start, _services)
                log.info("Module started: %s", mod.name)
            except Exception:
                log.exception("Failed to start module: %s", mod.name)

        log.info("── Phase 2a complete: %d modules started ────────────",
                 len(_modules))

        # ── Phase 2b: start_background on Job thread ─────────────────
        log.info("── Phase 2b: start_background (job thread) ──────────")

        for mod in _modules:
            try:
                mod.start_background(_services)
                log.info("Module background started: %s", mod.name)
            except Exception:
                log.exception("Failed to background-start module: %s",
                              mod.name)

        log.info("── Phase 2b complete: %d modules background started ─",
                 len(_modules))

        # Emit modules:started event
        if events_svc:
            events_svc.emit("modules:started",
                            modules=[m.name for m in _modules])

        _initialized = True
        log.info("Framework bootstrap complete: %d modules, %d tools",
                 len(_modules), len(_tools))


def shutdown():
    """Shut down all modules and services."""
    global _initialized

    for mod in reversed(_modules):
        try:
            mod.shutdown()
        except Exception:
            log.exception("Error shutting down module: %s", mod.name)

    if _services:
        _services.shutdown_all()

    _initialized = False


# ── UNO component registration ────────────────────────────────────────

try:
    import uno
    import unohelper
    from com.sun.star.task import XJobExecutor, XJob

    class MainJob(unohelper.Base, XJobExecutor, XJob):
        """UNO Job component — entry point for menu actions and OnStartApp."""

        def __init__(self, ctx):
            log.info("MainJob.__init__ called")
            self.ctx = ctx

        # ── XJob.execute (OnStartApp event) ──────────────────────────

        def execute(self, args):
            """Called by the Jobs framework on OnStartApp."""
            log.info("MainJob.execute (OnStartApp) called")
            try:
                bootstrap(self.ctx)
            except Exception:
                log.exception("MainJob.execute bootstrap FAILED")
            return ()

        # ── XJobExecutor.trigger (menu dispatch) ─────────────────────

        def trigger(self, args):
            """Dispatch commands from the extension UI."""
            log.info("MainJob.trigger called with: %r", args)
            try:
                bootstrap(self.ctx)

                command = args if isinstance(args, str) else ""

                if command in ("start_mcp", "ToggleMCPServer"):
                    self._toggle_mcp()
                elif command == "stop_mcp":
                    self._stop_mcp()
                elif command == "MCPStatus":
                    self._mcp_status()
                elif command == "About":
                    self._about()
                else:
                    log.info("MainJob.trigger unhandled: %s", command)
                    self._msgbox("Not implemented: %s" % command)
            except Exception:
                log.exception("MainJob.trigger FAILED")
                self._msgbox("Error: %s" % command)

        # ── UI helpers ─────────────────────────────────────────────

        def _msgbox(self, message, title="LocalWriter"):
            """Show a simple message box."""
            from plugin.framework.dialogs import msgbox
            msgbox(self.ctx, title, str(message))

        def _about(self):
            """Show the About dialog."""
            from plugin.framework.dialogs import about_dialog
            about_dialog(self.ctx)

        # ── HTTP / MCP helpers ───────────────────────────────────────

        def _get_module(self, name):
            for mod in _modules:
                if mod.name == name:
                    return mod
            return None

        def _toggle_mcp(self):
            http_mod = self._get_module("http")
            if http_mod is None:
                self._msgbox("HTTP module not found")
                return
            if http_mod._server and http_mod._server.is_running():
                log.info("Stopping HTTP server via toggle")
                http_mod._stop_server()
                self._msgbox("HTTP server stopped")
            else:
                log.info("Starting HTTP server via toggle")
                http_mod._start_server(get_services())
                if http_mod._server and http_mod._server.is_running():
                    status = http_mod._server.get_status()
                    self._msgbox("HTTP server started\n%s" % status.get("url", ""))
                else:
                    self._msgbox("HTTP server failed to start\nCheck ~/localwriter.log")

        def _stop_mcp(self):
            http_mod = self._get_module("http")
            if http_mod:
                http_mod._stop_server()
                self._msgbox("HTTP server stopped")

        def _mcp_status(self):
            http_mod = self._get_module("http")
            if http_mod and http_mod._server:
                status = http_mod._server.get_status()
                running = status.get("running", False)
                url = status.get("url", "?")
                routes = status.get("routes", 0)
                if running:
                    msg = "HTTP server running\nURL: %s\nRoutes: %d" % (url, routes)
                else:
                    msg = "HTTP server not running"
                self._msgbox(msg)
            else:
                self._msgbox("HTTP server is not running")

    # Register with LibreOffice
    g_ImplementationHelper = unohelper.ImplementationHelper()
    g_ImplementationHelper.addImplementation(
        MainJob,
        "org.extension.localwriter.Main",
        ("com.sun.star.task.Job",),
    )
    log.info("g_ImplementationHelper registered: org.extension.localwriter.Main")

    # Module-level fallback auto-bootstrap (like mcp-libre)
    def _module_autostart():
        import time
        time.sleep(3)
        if not _initialized:
            log.info("Module-level auto-bootstrap (fallback)")
            try:
                ctx = uno.getComponentContext()
                bootstrap(ctx)
            except Exception:
                log.exception("Module-level auto-bootstrap FAILED")

    threading.Thread(
        target=_module_autostart, daemon=True,
        name="localwriter-autoboot").start()
    log.info("Auto-bootstrap thread started (will fire in 3s)")

except ImportError as e:
    log.warning("UNO not available (not inside LO): %s", e)
except Exception as e:
    log.exception("UNO registration FAILED")
