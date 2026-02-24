"""ConfigService — namespaced config with access control.

Reads/writes localwriter.json in LibreOffice's user config directory.
Each module gets a ModuleConfigProxy that enforces namespace rules:
  - Read own keys: always OK
  - Read other module's public keys: OK
  - Read other module's private keys: ConfigAccessError
  - Write own keys: OK
  - Write other module's keys: ConfigAccessError
"""

import json
import logging
import os

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.config")

CONFIG_FILENAME = "localwriter.json"


class ConfigAccessError(Exception):
    """Raised when a module tries to access a private config key."""


class ConfigService(ServiceBase):
    name = "config"

    def __init__(self):
        self._ctx = None
        self._config_path = None
        self._defaults = {}  # "module.key" -> default_value
        self._manifest = {}  # "module.key" -> field schema
        self._events = None  # EventBus, set after init

    def initialize(self, ctx):
        self._ctx = ctx
        self._config_path = self._resolve_config_path(ctx)

    def set_events(self, events):
        """Wire the event bus (called during bootstrap after events service)."""
        self._events = events

    def set_manifest(self, manifest):
        """Load config schemas from the merged manifest.

        Args:
            manifest: dict from _manifest.py MODULES.
        """
        for mod_name, mod_data in manifest.items():
            for field_name, schema in mod_data.get("config", {}).items():
                full_key = f"{mod_name}.{field_name}"
                self._defaults[full_key] = schema.get("default")
                self._manifest[full_key] = schema

        # Apply overrides from env var LOCALWRITER_SET_CONFIG
        self._apply_env_overrides()

    def register_default(self, key, default):
        """Register a single default value."""
        self._defaults[key] = default

    # ── Read/Write ────────────────────────────────────────────────────

    def get(self, key, caller_module=None):
        """Get a config value. Returns default if not set.

        Args:
            key:           Full key "module.field" or short key "field"
                           (when called via ModuleConfigProxy).
            caller_module: Name of the calling module (for access control).
        """
        self._check_read_access(key, caller_module)
        data = self._read_file()
        if key in data:
            return data[key]
        return self._defaults.get(key)

    def get_dict(self):
        """Return the full config as a dict (no access control)."""
        return self._read_file()

    def set(self, key, value, caller_module=None):
        """Set a config value and emit config:changed event.

        Args:
            key:           Full key "module.field".
            value:         New value.
            caller_module: Name of the calling module (for access control).
        """
        self._check_write_access(key, caller_module)
        data = self._read_file()
        old_value = data.get(key, self._defaults.get(key))
        data[key] = value
        self._write_file(data)

        if self._events and value != old_value:
            self._events.emit(
                "config:changed", key=key, value=value, old_value=old_value
            )

    def remove(self, key, caller_module=None):
        """Remove a config key."""
        self._check_write_access(key, caller_module)
        data = self._read_file()
        if key in data:
            del data[key]
            self._write_file(data)

    # ── Access control ────────────────────────────────────────────────

    def _check_read_access(self, key, caller_module):
        if caller_module is None:
            return  # No caller tracking = no restriction
        if "." not in key:
            return  # Short key = own module
        module = key.split(".", 1)[0]
        if module == caller_module:
            return
        schema = self._manifest.get(key, {})
        if not schema.get("public", False):
            raise ConfigAccessError(
                f"Module '{caller_module}' cannot read private config '{key}'"
            )

    def _check_write_access(self, key, caller_module):
        if caller_module is None:
            return
        if "." not in key:
            return
        module = key.split(".", 1)[0]
        if module != caller_module:
            raise ConfigAccessError(
                f"Module '{caller_module}' cannot write to '{key}'"
            )

    # ── Environment overrides ────────────────────────────────────────

    def _apply_env_overrides(self):
        """Apply config overrides from LOCALWRITER_SET_CONFIG env var.

        Format: "key=value,key=value,..."
        Values are coerced to the type declared in the module schema.
        Overrides are persisted to the config file.
        """
        raw = os.environ.get("LOCALWRITER_SET_CONFIG", "").strip()
        if not raw:
            return

        data = self._read_file()
        count = 0
        for pair in raw.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, raw_value = pair.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()

            value = self._coerce_value(key, raw_value)
            data[key] = value
            count += 1
            log.info("Config override: %s = %r", key, value)

        if count:
            self._write_file(data)
            log.info("Persisted %d config override(s) from LOCALWRITER_SET_CONFIG",
                     count)

    def _coerce_value(self, key, raw):
        """Coerce a string value to the type declared in the manifest schema."""
        schema = self._manifest.get(key, {})
        declared_type = schema.get("type", "string")

        if declared_type == "boolean":
            return raw.lower() in ("true", "1", "yes", "on")
        if declared_type == "int":
            try:
                return int(raw)
            except ValueError:
                return raw
        if declared_type == "float":
            try:
                return float(raw)
            except ValueError:
                return raw
        return raw

    # ── File I/O ──────────────────────────────────────────────────────

    def _resolve_config_path(self, ctx):
        try:
            import uno
            sm = ctx.getServiceManager()
            path_settings = sm.createInstanceWithContext(
                "com.sun.star.util.PathSettings", ctx
            )
            user_config = getattr(path_settings, "UserConfig", "")
            if user_config and str(user_config).startswith("file://"):
                user_config = str(uno.fileUrlToSystemPath(user_config))
            return os.path.join(user_config, CONFIG_FILENAME)
        except Exception:
            log.warning("Could not resolve LO config path, using fallback")
            return os.path.join(os.path.expanduser("~"), ".config", CONFIG_FILENAME)

    def _read_file(self):
        if not self._config_path or not os.path.exists(self._config_path):
            return {}
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return {}

    def _write_file(self, data):
        if not self._config_path:
            return
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except IOError:
            log.exception("Error writing config to %s", self._config_path)

    # ── Module proxy factory ──────────────────────────────────────────

    def proxy_for(self, module_name):
        """Create a ModuleConfigProxy scoped to *module_name*."""
        return ModuleConfigProxy(self, module_name)


class ModuleConfigProxy:
    """Scoped config access for a single module.

    When ``get("port")`` is called (no dot), it auto-prefixes with the
    module name → ``"mcp.port"``.

    Cross-module reads require the full key: ``get("openai_compat.endpoint")``.
    """

    __slots__ = ("_config", "_module")

    def __init__(self, config_service, module_name):
        self._config = config_service
        self._module = module_name

    def get(self, key, default=None):
        if "." not in key:
            key = f"{self._module}.{key}"
        try:
            val = self._config.get(key, caller_module=self._module)
            return val if val is not None else default
        except ConfigAccessError:
            raise
        except Exception:
            return default

    def set(self, key, value):
        if "." not in key:
            key = f"{self._module}.{key}"
        self._config.set(key, value, caller_module=self._module)

    def remove(self, key):
        if "." not in key:
            key = f"{self._module}.{key}"
        self._config.remove(key, caller_module=self._module)
