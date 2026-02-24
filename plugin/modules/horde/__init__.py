"""AI Horde image generation backend module."""

from plugin.framework.module_base import ModuleBase


class HordeModule(ModuleBase):
    """Registers an AI Horde image provider."""

    def initialize(self, services):
        from plugin.modules.horde.provider import HordeProvider

        self._provider = HordeProvider(services.config.proxy_for(self.name))
        services.image.register_provider("horde", self._provider)
