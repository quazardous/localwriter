"""AI module — unified AI provider registry and model catalog."""

from plugin.framework.module_base import ModuleBase


class Module(ModuleBase):

    def initialize(self, services):
        from plugin.modules.ai.service import AiService

        ai = AiService()
        ai.set_config(services.config)
        services.register(ai)
