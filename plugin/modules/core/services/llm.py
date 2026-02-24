"""LlmService — interface and router for LLM backends.

This service defines the contract that LLM backend modules (openai_compat,
ollama, etc.) must implement. It routes calls to the active provider
based on config.
"""

import logging
from abc import ABC, abstractmethod

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.llm")


class LlmProvider(ABC):
    """Interface that backend modules implement and register."""

    name: str = None

    @abstractmethod
    def stream(self, messages, tools=None, **kwargs):
        """Stream a chat completion.

        Args:
            messages: List of message dicts (OpenAI format).
            tools:    Optional list of tool schemas (OpenAI format).
            **kwargs: Extra params (temperature, max_tokens, etc.)

        Yields:
            Chunks (format depends on implementation, but should include
            delta content and tool calls).
        """

    @abstractmethod
    def complete(self, messages, tools=None, **kwargs):
        """Non-streaming completion. Returns full response dict."""

    def supports_tools(self):
        """Whether this provider supports tool calling."""
        return True

    def supports_vision(self):
        """Whether this provider supports image inputs."""
        return False


class LlmService(ServiceBase):
    """Router that delegates to the active LLM provider.

    Backend modules register themselves during initialization::

        services.llm.register_provider("openai_compat", MyProvider())

    The active provider is determined by config (``core.llm_backend``).
    """

    name = "llm"

    def __init__(self):
        self._providers = {}  # name -> LlmProvider
        self._config = None

    def set_config(self, config):
        self._config = config

    def register_provider(self, name, provider):
        """Register an LLM provider (called by backend modules)."""
        self._providers[name] = provider
        log.info("LLM provider registered: %s", name)

    def get_provider(self, name=None):
        """Get a provider by name, or the active one from config."""
        if name is None:
            name = self._get_active_name()
        return self._providers.get(name)

    @property
    def available_providers(self):
        return list(self._providers.keys())

    def stream(self, messages, tools=None, **kwargs):
        """Stream via the active provider."""
        provider = self._get_active_provider()
        return provider.stream(messages, tools=tools, **kwargs)

    def complete(self, messages, tools=None, **kwargs):
        """Complete via the active provider."""
        provider = self._get_active_provider()
        return provider.complete(messages, tools=tools, **kwargs)

    def supports_tools(self):
        provider = self.get_provider()
        return provider.supports_tools() if provider else False

    # ── Internal ──────────────────────────────────────────────────────

    def _get_active_name(self):
        if self._config:
            return self._config.get("core.llm_backend", caller_module=None) or "openai_compat"
        return "openai_compat"

    def _get_active_provider(self):
        name = self._get_active_name()
        provider = self._providers.get(name)
        if provider is None:
            available = ", ".join(self._providers.keys()) or "(none)"
            raise RuntimeError(
                f"LLM provider '{name}' not registered. Available: {available}"
            )
        return provider
