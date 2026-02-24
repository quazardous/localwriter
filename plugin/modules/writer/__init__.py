"""Writer module — tools for Writer document manipulation."""

from plugin.framework.module_base import ModuleBase


class WriterModule(ModuleBase):
    """Registers Writer tools for outline, content, comments, styles, etc."""

    def initialize(self, services):
        self.services = services
