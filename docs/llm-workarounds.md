# LLM Workarounds

Workarounds for LLM quirks when interacting with LibreOffice tools.

## Calc: CSV delimiter handling

LLMs are inconsistent with CSV delimiters. Since Calc uses semicolons (`;`) for formula arguments, models often use them for CSV data too.

**Workaround**: `import_csv_from_string` auto-detects the delimiter by peeking at the first few lines. If semicolons outnumber commas, it switches to `;`.

## Calc: semicolon splitting in range writes

Models often send `"Name;Age;Salary"` instead of `["Name", "Age", "Salary"]` to `write_formula_range`.

**Workaround**: The parser detects raw semicolon-separated strings (skipping formulas starting with `=`) and splits them using `csv.reader` with quote awareness.

## Calc: formula-safe JSON normalization

Models use semicolons inside JSON arrays (e.g. `["A"; "B"]`). A blind `replace(";", ",")` would break formulas that need semicolons.

**Workaround**: Regex replaces semicolons only outside double quotes: `re.sub(r';(?=(?:[^"]*"[^"]*")*[^"]*$)', ',', s)`.

## Calc: formula syntax in prompts

LibreOffice requires semicolons as formula argument separators. Wrong: `=SUM(A1,A10)`.

**Workaround**: System prompt includes explicit rules:
- "FORMULA SYNTAX: LibreOffice uses semicolon (;) as the formula argument separator"
- "CSV DATA: Use comma (,) for import_csv_from_string"

## Defensive parameter handling

Models sometimes pass range names as lists or wrap them in extra quotes.

**Workaround**: Tool dispatchers check if `range_name` is a list or string and loop automatically rather than crashing.

## Streaming edge cases

Adopted from LiteLLM analysis (see `legacy_docs/dev/litellm-integration.md` for full references):

1. **`finish_reason="error"`** — treated as hard failure, shown to user
2. **Repeated identical chunks** — detected after 20 identical chunks, raises error
3. **`finish_reason="stop"` with tool_calls** — remapped to `"tool_calls"` so tool loop executes
4. **Delta normalization** — `role`, `tool.type`, `function.arguments` can be `None` from some providers; normalized to defaults
