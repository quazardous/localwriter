"""ImageService — interface and router for image generation backends.

Same pattern as LlmService: defines the contract, backend modules
(horde, endpoint, etc.) register providers.
"""

import logging
from abc import ABC, abstractmethod

from plugin.framework.service_base import ServiceBase

log = logging.getLogger("localwriter.image")


class ImageProvider(ABC):
    """Interface that image backend modules implement."""

    name: str = None

    @abstractmethod
    def generate(self, prompt, **kwargs):
        """Generate an image from a text prompt.

        Args:
            prompt: Text description of the image.
            **kwargs: width, height, model, strength, etc.

        Returns:
            (file_paths: list[str], error: str | None)
            file_paths is a list of generated image paths.
            error is None on success.
        """

    def supports_editing(self):
        """Whether this provider supports image editing (img2img)."""
        return False


class ImageService(ServiceBase):
    """Router that delegates to the active image provider."""

    name = "image"

    def __init__(self):
        self._providers = {}
        self._config = None

    def set_config(self, config):
        self._config = config

    def register_provider(self, name, provider):
        self._providers[name] = provider
        log.info("Image provider registered: %s", name)

    def get_provider(self, name=None):
        if name is None:
            name = self._get_active_name()
        return self._providers.get(name)

    @property
    def available_providers(self):
        return list(self._providers.keys())

    def generate(self, prompt, provider_name=None, **kwargs):
        """Generate an image via the specified or active provider.

        Returns:
            (file_paths: list[str], error: str | None)
        """
        name = provider_name or self._get_active_name()
        provider = self._providers.get(name)
        if provider is None:
            return [], f"Image provider '{name}' not registered"
        return provider.generate(prompt, **kwargs)

    def _get_active_name(self):
        if self._config:
            return self._config.get("core.image_backend", caller_module=None) or "horde"
        return "horde"
