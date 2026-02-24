"""AI chat sidebar module."""

import logging

from plugin.framework.module_base import ModuleBase

log = logging.getLogger("localwriter.chatbot")


class ChatbotModule(ModuleBase):
    """Registers the chatbot sidebar and its tool adapter."""

    def initialize(self, services):
        self._services = services

        # Create the tool adapter for routing chat tool calls
        from plugin.modules.chatbot.panel import ChatToolAdapter
        self._adapter = ChatToolAdapter(services.tools, services)

    def get_adapter(self):
        """Return the ChatToolAdapter for use by the panel factory."""
        return self._adapter
