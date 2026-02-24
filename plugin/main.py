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

_log_path = os.path.join(os.path.expanduser("~"), "localwriter.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(_log_path, mode="w", encoding="utf-8"),
    ],
)

log = logging.getLogger("localwriter.main")
log.info("=== main.py loaded ===")

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
    package = "plugin.modules.%s" % name
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

        from plugin.framework.service_registry import ServiceRegistry
        from plugin.framework.tool_registry import ToolRegistry

        _services = ServiceRegistry()
        _tools = ToolRegistry(_services)

        # Register the tool registry itself as a service
        _services.register_instance("tools", _tools)

        # Load and sort modules
        manifests = _load_manifest()

        manifest_dict = {m["name"]: m for m in manifests}

        for manifest in manifests:
            name = manifest["name"]
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

            # After core registers config service, initialize it with ctx
            # and load all config defaults so subsequent modules can read
            # their config during init
            if name == "core":
                config_svc = _services.get("config")
                if config_svc:
                    if ctx:
                        config_svc.initialize(ctx)
                    config_svc.set_manifest(manifest_dict)
                    log.info("Config defaults loaded for %d modules",
                             len(manifest_dict))

            # Auto-discover tools from this module's tools/ subpackage
            tools_dir = os.path.join(
                os.path.dirname(__file__), "modules", name, "tools")
            if os.path.isdir(tools_dir):
                tools_pkg = "plugin.modules.%s.tools" % name
                _tools.discover(tools_dir, tools_pkg)

        # Wire event bus into config service
        if config_svc:
            events_svc = _services.get("events")
            if events_svc:
                config_svc.set_events(events_svc)

        # Initialize services that need a UNO context
        if ctx:
            _services.initialize_all(ctx)

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
                elif command == "settings":
                    self._show_settings()
                elif command == "MCPStatus":
                    self._mcp_status()
                else:
                    log.info("MainJob.trigger unhandled: %s", command)
            except Exception:
                log.exception("MainJob.trigger FAILED")

        # ── MCP helpers ──────────────────────────────────────────────

        def _get_mcp_module(self):
            for mod in _modules:
                if mod.name == "mcp":
                    return mod
            return None

        def _toggle_mcp(self):
            mcp = self._get_mcp_module()
            if mcp is None:
                log.error("MCP module not found")
                return
            if mcp._server and mcp._server.is_running():
                log.info("Stopping MCP server via toggle")
                mcp._stop_server()
            else:
                log.info("Starting MCP server via toggle")
                mcp._start_server(get_services())

        def _stop_mcp(self):
            mcp = self._get_mcp_module()
            if mcp:
                mcp._stop_server()

        def _mcp_status(self):
            mcp = self._get_mcp_module()
            if mcp and mcp._server:
                status = mcp._server.get_status()
                log.info("MCP status: %s", status)
            else:
                log.info("MCP server is not running")

        def _show_settings(self):
            from plugin.modules.core.settings_dialog import show_settings
            from plugin._manifest import MODULES
            config_svc = get_services().config
            show_settings(self.ctx, config_svc, MODULES)

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
