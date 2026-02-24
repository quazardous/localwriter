"""OpenAI-compatible LLM backend module."""

from plugin.framework.module_base import ModuleBase


class OpenAICompatModule(ModuleBase):
    """Registers an OpenAI-compatible LLM provider."""

    def initialize(self, services):
        from plugin.modules.openai_compat.provider import OpenAICompatProvider

        self._provider = OpenAICompatProvider(services.config.proxy_for(self.name))
        services.llm.register_provider("openai_compat", self._provider)

    def shutdown(self):
        if hasattr(self, "_provider"):
            self._provider.close()
