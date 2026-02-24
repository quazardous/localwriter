"""Page/slide management tools for Draw/Impress documents."""

from plugin.framework.tool_base import ToolBase


class AddSlide(ToolBase):
    name = "add_slide"
    description = "Inserts a new slide (page) at the specified index."
    parameters = {
        "type": "object",
        "properties": {
            "index": {
                "type": "integer",
                "description": "Index where to insert (end if omitted)",
            }
        },
        "required": [],
    }
    doc_types = ["draw"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        from plugin.modules.draw.bridge import DrawBridge
        bridge = DrawBridge(ctx.doc)
        bridge.create_slide(kwargs.get("index"))
        return {"status": "ok", "message": "Slide added"}


class DeleteSlide(ToolBase):
    name = "delete_slide"
    description = "Deletes the slide (page) at the specified index."
    parameters = {
        "type": "object",
        "properties": {
            "index": {
                "type": "integer",
                "description": "Index of slide to delete",
            }
        },
        "required": ["index"],
    }
    doc_types = ["draw"]
    is_mutation = True

    def execute(self, ctx, **kwargs):
        from plugin.modules.draw.bridge import DrawBridge
        bridge = DrawBridge(ctx.doc)
        bridge.delete_slide(kwargs["index"])
        return {"status": "ok", "message": "Slide deleted"}
