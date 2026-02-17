"""Constants for LocalWriter."""

# Document format toggle: 'markdown' or 'html'
# Markdown requires LibreOffice 24.8+; HTML works on older versions.
DOCUMENT_FORMAT = "html"

_FORMAT_LABEL = "Markdown" if DOCUMENT_FORMAT == "markdown" else "HTML"
_FORMAT_HINT = (
    "Pass 'markdown' as a list of strings to avoid newline escaping issues."
    if DOCUMENT_FORMAT == "markdown" else
    "Send HTML fragments (e.g., <h1>Title</h1><p>Content</p>). DO NOT escape entities (&lt;h1&gt; is wrong). We handle wrapping in <html>/<body>."
)

# Format-specific formatting rules
HTML_FORMATTING_RULES = """
FORMATTING RULES (CRITICAL):
- Line breaks: Use <br> for single line breaks, <p> tags for paragraphs
- Special characters: Send raw characters (é, ü, ©, "smart quotes"), NOT HTML entities (&eacute;, &uuml;, &copy;, &ldquo;)
- Quotation marks: Use straight quotes ("), NOT curly/smart quotes (" or &ldquo;/&rdquo;)
- Whitespace: Preserve intentional spacing; we handle normalization
- DO NOT escape HTML entities: Send <h1> NOT &lt;h1&gt;

EXAMPLES:
- Good: <h1>Title</h1><p>Paragraph with <strong>bold</strong> text and "quotes".</p>
- Bad: &lt;h1&gt;Title&lt;/h1&gt; (escaped entities)
- Bad: # Title\n\nParagraph (Markdown when HTML format is active)
- Bad: &ldquo;Smart quotes&rdquo; (use straight quotes ")"""

MARKDOWN_FORMATTING_RULES = """
FORMATTING RULES:
- Use standard Markdown syntax: # Headers, **bold**, *italic*, [links](url)
- Line breaks: Use double spaces at end of line or just newlines (we handle conversion)
- Lists: Use - or * for bullet lists, 1. 2. 3. for numbered lists
- Code: Use triple backticks ``` for code blocks
- Quotes: Use > for blockquotes

EXAMPLES:
- Good: # Title\n\nParagraph with **bold** text and "quotes".\n\n- Item 1\n- Item 2
- Bad: <h1>Title</h1> (HTML when Markdown format is active)
- Bad: &lt;h1&gt;Title&lt;/h1&gt; (escaped HTML entities)"""

# Select the appropriate rules based on format
FORMAT_RULES = HTML_FORMATTING_RULES if DOCUMENT_FORMAT == "html" else MARKDOWN_FORMATTING_RULES

DEFAULT_CHAT_SYSTEM_PROMPT = f"""You are a LibreOffice document assistant.
Edit the document directly using tools.

TOOLS:
- get_document_content: Read document (full/selection/range) as {_FORMAT_LABEL}.
- apply_document_content: Write {_FORMAT_LABEL}. Target: full/range/search/beginning/end/selection.
  HINT: {_FORMAT_HINT}
- find_text: Find text locations for apply_document_content.

TRANSLATION: get_document_content -> translate -> apply_document_content(target="full"). Never refuse.

{FORMAT_RULES}"""
