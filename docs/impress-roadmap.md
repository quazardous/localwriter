# Impress Tools Roadmap

Vision for AI-driven presentation capabilities, extending the existing Draw module.

## Current capabilities (shared with Draw)

- `create_shape` — rectangles, ellipses, text boxes, lines
- `edit_shape` — move, resize, recolor, change text
- `delete_shape` — remove shapes
- `get_draw_summary` — list shapes and properties on current slide
- `list_pages` / `add_slide` / `delete_slide` — basic slide management

## Near term: slide & layout management

- `add_slide(index, layout)` — insert with chosen layout (Title Slide, Title and Content, etc.)
- `reorder_slides(from_index, to_index)` — change slide sequence
- `duplicate_slide(index)` — clone slides for templating
- `list_master_slides()` / `apply_master_slide(master_name, page_index)` — theme management

## Medium term: content & context

- `get_notes(page_index)` / `set_notes(text, page_index)` — speaker notes
- `get_slide_content_full(page_index)` — structured text (title, bullets, subtitles)
- `create_table` — native Impress table support

## Long term: generative workflows

- Outline-to-deck conversion from Writer documents
- AI slide audits (text density, contrast, visual balance)
- Image generation for slide content
- Presentation controls (`start_presentation`, `goto_slide`)

## Implementation note

Prefer `com.sun.star.presentation` services when available, fall back to the drawing layer for fine-grained shape control.
