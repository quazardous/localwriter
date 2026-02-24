"""Base class for all modules."""

from abc import ABC


class ModuleBase(ABC):
    """Base class for all LocalWriter modules.

    Modules declare their manifest in module.yaml (config, requires,
    provides_services). This class handles the runtime behavior:
    initialization, event wiring, and shutdown.

    The ``name`` attribute is set automatically from _manifest.py at load
    time — it does NOT need to be set in the subclass.
    """

    name: str = None

    def initialize(self, services):
        """Phase 1: Called in dependency order during bootstrap.

        Use this to register services, wire event subscriptions, and
        create internal objects. All core services are available.

        Args:
            services: ServiceRegistry with attribute access to all
                      registered services (services.config, services.events …).
        """

    def start(self, services):
        """Phase 2a: Called on the VCL main thread after ALL modules
        have initialized.

        Safe for UNO operations: document listeners, UI setup, toolkit
        calls. Dispatched via execute_on_main_thread (blocking).
        Called in dependency order.

        Args:
            services: ServiceRegistry with attribute access to all
                      registered services.
        """

    def start_background(self, services):
        """Phase 2b: Called on the Job thread after all start() complete.

        Launch background tasks: HTTP servers, LLM connections, polling.
        Called in dependency order.

        Args:
            services: ServiceRegistry with attribute access to all
                      registered services.
        """

    def shutdown(self):
        """Stop background tasks, close connections.

        Called in reverse dependency order on extension unload."""
