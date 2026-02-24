"""Ollama local LLM backend module."""

from plugin.framework.module_base import ModuleBase


class OllamaModule(ModuleBase):
    """Registers an Ollama LLM provider."""

    def initialize(self, services):
        from plugin.modules.ollama.provider import OllamaProvider

        self._provider = OllamaProvider(services.config.proxy_for(self.name))
        services.llm.register_provider("ollama", self._provider)

    def shutdown(self):
        if hasattr(self, "_provider"):
            self._provider.close()
