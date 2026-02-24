"""XContainerWindowEventHandler for Tools > Options > LocalWriter pages.

Each module with config gets its own Options page (XDL generated at build time).
A hidden ``__module__`` control in each XDL identifies which module the page belongs to.

The handler reads/writes config via ConfigService and emits config:changed events.

This file is registered as a UNO component in META-INF/manifest.xml.
"""

import logging
import os
import sys

# Ensure plugin parent is on path so "plugin.xxx" imports work
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_plugin_dir)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import unohelper
from com.sun.star.awt import XContainerWindowEventHandler, XActionListener
from com.sun.star.lang import XServiceInfo

log = logging.getLogger("localwriter.options")


class _BrowseListener(unohelper.Base, XActionListener):
    """Opens a FilePicker and writes the result to a paired textfield."""

    def __init__(self, text_ctrl, widget, file_filter=""):
        self._text_ctrl = text_ctrl
        self._widget = widget  # "file" or "folder"
        self._file_filter = file_filter

    def actionPerformed(self, evt):
        try:
            from plugin.framework.uno_context import get_ctx
            ctx = get_ctx()
            if not ctx:
                return
            smgr = ctx.ServiceManager
            if self._widget == "folder":
                picker = smgr.createInstanceWithContext(
                    "com.sun.star.ui.dialogs.FolderPicker", ctx)
                current = self._text_ctrl.getModel().Text
                if current:
                    import uno
                    picker.setDisplayDirectory(
                        uno.systemPathToFileUrl(current))
                if picker.execute() == 1:
                    import uno
                    path = uno.fileUrlToSystemPath(picker.getDirectory())
                    self._text_ctrl.getModel().Text = path
            else:
                picker = smgr.createInstanceWithContext(
                    "com.sun.star.ui.dialogs.FilePicker", ctx)
                if self._file_filter:
                    parts = self._file_filter.split("|")
                    for i in range(0, len(parts) - 1, 2):
                        picker.appendFilter(parts[i].strip(),
                                            parts[i + 1].strip())
                current = self._text_ctrl.getModel().Text
                if current:
                    import uno
                    import os
                    parent = os.path.dirname(current)
                    if parent:
                        picker.setDisplayDirectory(
                            uno.systemPathToFileUrl(parent))
                if picker.execute() == 1:
                    import uno
                    files = picker.getFiles()
                    if files:
                        path = uno.fileUrlToSystemPath(files[0])
                        self._text_ctrl.getModel().Text = path
        except Exception:
            log.exception("Browse action failed")

    def disposing(self, evt):
        pass


class OptionsHandler(unohelper.Base, XContainerWindowEventHandler, XServiceInfo):
    """Handles initialize / ok / back events for all LocalWriter Options pages."""

    IMPLE_NAME = "org.extension.localwriter.OptionsHandler"
    SERVICE_NAMES = (IMPLE_NAME,)

    def __init__(self, ctx):
        self.ctx = ctx
        self._cached_values = {}  # full_key -> value at init time

    # ── XContainerWindowEventHandler ─────────────────────────────────

    def callHandlerMethod(self, xWindow, eventObject, methodName):
        log.debug("OptionsHandler: method=%s event=%s", methodName, eventObject)
        if methodName != "external_event":
            return False
        try:
            if eventObject == "initialize":
                self._on_initialize(xWindow)
                return True
            elif eventObject == "ok":
                self._on_ok(xWindow)
                return True
            elif eventObject == "back":
                self._on_back(xWindow)
                return True
        except Exception:
            log.exception("OptionsHandler event '%s' failed", eventObject)
        return False

    def getSupportedMethodNames(self):
        return ("external_event",)

    # ── XServiceInfo ─────────────────────────────────────────────────

    def supportsService(self, name):
        return name in self.SERVICE_NAMES

    def getImplementationName(self):
        return self.IMPLE_NAME

    def getSupportedServiceNames(self):
        return self.SERVICE_NAMES

    # ── Event handlers ───────────────────────────────────────────────

    def _on_initialize(self, xWindow):
        """Load config values into the Options page controls."""
        module_name = self._detect_module(xWindow)
        log.info("Options page initialize: module=%s", module_name)
        if not module_name:
            log.warning("Could not detect module from Options page")
            return

        manifest = self._get_manifest()
        mod_config = self._get_module_config(manifest, module_name)
        if not mod_config:
            return

        config_svc = self._get_config_service()

        for field_name, schema in mod_config.items():
            full_key = "%s.%s" % (module_name, field_name)
            widget = schema.get("widget", "text")

            # Read via ConfigService (uses global ctx via get_ctx())
            val = config_svc.get(full_key) if config_svc else None
            if val is None:
                val = schema.get("default")

            self._cached_values[full_key] = val

            ctrl = self._get_control(xWindow, field_name)
            if ctrl is None:
                continue

            try:
                if widget == "checkbox":
                    ctrl.getModel().State = 1 if val else 0
                elif widget in ("text", "password", "file", "folder"):
                    ctrl.getModel().Text = str(val) if val else ""
                elif widget == "textarea":
                    ctrl.getModel().Text = str(val) if val else ""
                elif widget in ("number", "slider"):
                    ctrl.getModel().Value = float(val) if val is not None else 0
                elif widget == "select":
                    resolved = self._resolve_options(schema)
                    self._populate_select(ctrl, resolved, val)
            except Exception:
                log.exception("Error loading %s", full_key)

            # Wire browse button for file/folder widgets
            if widget in ("file", "folder"):
                btn = self._get_control(xWindow, "btn_%s" % field_name)
                if btn and ctrl:
                    btn.addActionListener(_BrowseListener(
                        ctrl, widget, schema.get("file_filter", "")))

    def _on_ok(self, xWindow):
        """Write control values via ConfigService and emit event."""
        module_name = self._detect_module(xWindow)
        if not module_name:
            return

        manifest = self._get_manifest()
        mod_config = self._get_module_config(manifest, module_name)
        if not mod_config:
            return

        config_svc = self._get_config_service()
        if not config_svc:
            log.error("_on_ok: ConfigService not available")
            return

        changes = {}
        for field_name, schema in mod_config.items():
            full_key = "%s.%s" % (module_name, field_name)
            widget = schema.get("widget", "text")
            field_type = schema.get("type", "string")

            ctrl = self._get_control(xWindow, field_name)
            if ctrl is None:
                continue

            try:
                resolved = self._resolve_options(schema) if widget == "select" else schema
                new_val = self._read_control(ctrl, widget, field_type, resolved)
                changes[full_key] = new_val
            except Exception:
                log.exception("_on_ok: read control FAILED for %s", full_key)

        if changes:
            diffs = config_svc.set_batch(changes, old_values=self._cached_values)
            # Update cache with new values
            for key, val in changes.items():
                self._cached_values[key] = val
            if diffs:
                log.info("_on_ok: %d change(s) saved for %s", len(diffs), module_name)

    def _on_back(self, xWindow):
        """Reload values (revert unsaved changes)."""
        self._on_initialize(xWindow)

    # ── Helpers ──────────────────────────────────────────────────────

    def _read_control(self, ctrl, widget, field_type, schema):
        """Read the current value from a control."""
        if widget == "checkbox":
            return ctrl.getModel().State == 1
        elif widget in ("text", "password", "textarea", "file", "folder"):
            return ctrl.getModel().Text or ""
        elif widget in ("number", "slider"):
            raw = ctrl.getModel().Value
            return int(raw) if field_type == "int" else float(raw)
        elif widget == "select":
            return self._read_select(ctrl, schema)
        return ctrl.getModel().Text or ""

    def _detect_module(self, xWindow):
        """Read the hidden __module__ control to find which module this page is for.

        dlg:text controls expose their dlg:value via the Label property on the model.
        """
        try:
            ctrl = xWindow.getControl("__module__")
            if ctrl:
                model = ctrl.getModel()
                # dlg:text (XFixedText) stores dlg:value in Label, not Text
                return getattr(model, "Label", "") or getattr(model, "Text", "")
        except Exception:
            log.exception("_detect_module failed")
        return None

    def _get_control(self, xWindow, field_name):
        """Get a control by field name, returning None if missing."""
        try:
            return xWindow.getControl(field_name)
        except Exception:
            return None

    def _get_config_service(self):
        """Get the ConfigService from the framework."""
        try:
            from plugin.main import get_services
            services = get_services()
            return services.config if services else None
        except Exception:
            log.exception("Could not get ConfigService")
            return None

    def _get_manifest(self):
        """Get the manifest modules list."""
        try:
            from plugin._manifest import MODULES
            return MODULES
        except ImportError:
            return []

    def _get_module_config(self, manifest, module_name):
        """Find the config dict for a given module name."""
        for m in manifest:
            if m.get("name") == module_name:
                return m.get("config", {})
        return {}

    def _resolve_options(self, schema):
        """If schema has an options_provider, call it to get dynamic options."""
        provider_path = schema.get("options_provider")
        if not provider_path:
            return schema
        try:
            options = self._call_options_provider(provider_path)
            return dict(schema, options=options)
        except Exception:
            log.exception("Failed to resolve options_provider: %s", provider_path)
            return schema

    def _call_options_provider(self, provider_path):
        """Import a module and call a function to get options.

        provider_path format: "plugin.modules.tunnel:get_provider_options"
        Returns a list of {"value": ..., "label": ...} dicts.
        """
        module_path, func_name = provider_path.rsplit(":", 1)
        import importlib
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        return func()

    def _populate_select(self, ctrl, schema, current_value):
        """Populate a menulist/listbox with options and select current value."""
        options = schema.get("options", [])
        if not options:
            return

        labels = tuple(o.get("label", o.get("value", "")) for o in options)
        values = [o.get("value", "") for o in options]

        model = ctrl.getModel()
        model.StringItemList = labels

        if current_value in values:
            ctrl.selectItemPos(values.index(current_value), True)
        elif options:
            ctrl.selectItemPos(0, True)

    def _read_select(self, ctrl, schema):
        """Read the selected value from a menulist/listbox."""
        options = schema.get("options", [])
        sel = ctrl.getSelectedItemPos()
        if 0 <= sel < len(options):
            return options[sel].get("value", "")
        return schema.get("default", "")


# ── UNO component registration ──────────────────────────────────────

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    OptionsHandler,
    OptionsHandler.IMPLE_NAME,
    OptionsHandler.SERVICE_NAMES,
)
