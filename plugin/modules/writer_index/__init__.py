"""Writer full-text search sub-module with stemming."""

from plugin.framework.module_base import ModuleBase


class WriterIndexModule(ModuleBase):
    """Registers the IndexService for full-text search."""

    def initialize(self, services):
        from .services.index import IndexService

        idx = IndexService(services.document, services.writer_tree,
                           services.writer_bookmarks, services.events)
        services.register_instance("writer_index", idx)
