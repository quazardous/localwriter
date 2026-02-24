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

    # ── Action dispatch ──────────────────────────────────────────────

    def on_action(self, action):
        if action == "extend_selection":
            self._action_extend_selection()
        elif action == "edit_selection":
            self._action_edit_selection()
        else:
            super().on_action(action)

    def _action_extend_selection(self):
        log.info("Extend selection triggered")
        events = getattr(self._services, "events", None)
        if events:
            events.emit("chatbot:extend_selection")

    def _action_edit_selection(self):
        log.info("Edit selection triggered")
        events = getattr(self._services, "events", None)
        if events:
            events.emit("chatbot:edit_selection")
