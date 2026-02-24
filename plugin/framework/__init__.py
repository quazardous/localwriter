"""LocalWriter framework — base classes, registries, event bus."""

from plugin.framework.module_base import ModuleBase
from plugin.framework.tool_base import ToolBase
from plugin.framework.tool_context import ToolContext
from plugin.framework.service_base import ServiceBase
from plugin.framework.service_registry import ServiceRegistry
from plugin.framework.tool_registry import ToolRegistry
from plugin.framework.event_bus import EventBus
from plugin.framework.schema_convert import to_openai_schema, to_mcp_schema

__all__ = [
    "ModuleBase",
    "ToolBase",
    "ToolContext",
    "ServiceBase",
    "ServiceRegistry",
    "ToolRegistry",
    "EventBus",
    "to_openai_schema",
    "to_mcp_schema",
]
