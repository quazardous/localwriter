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
        """Called after all services are registered.

        Use this to wire event subscriptions, create internal objects,
        and register service providers (for backend modules).

        Args:
            services: ServiceRegistry with attribute access to all
                      registered services (services.config, services.events …).
        """

    def shutdown(self):
        """Called on extension unload. Override to clean up resources."""
