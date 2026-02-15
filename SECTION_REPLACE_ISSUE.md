# Section replace issue (handoff for fresh instance)

**Summary:** Section replacement (e.g. "Convert my Summary section to Finnish") fails when the model uses `apply_markdown(target="search")` with the full section text (heading + paragraph(s)). We want to **support** long / multi-paragraph search strings, not give up and steer to find_text + range.

## Root cause (current understanding)

LibreOffice Writer's **regex** search only matches within a single paragraph. Literal search may also behave differently depending on how paragraph/line breaks are stored (\n, \n\n, \r\n, etc.). So when the section spans multiple paragraphs, the single literal "plain" and the line-break fuzzy regex candidate we try may not match the document's actual break representation.

## Desired approach: work around it

**Try different types of CR/LF (and newline) variants** as literal search candidates so that one of them matches how the document stores paragraph/line boundaries. That way we keep supporting long search/replace strings that can easily be multiple paragraphs, instead of treating "multi-paragraph" as unsupported and telling the model to use find_text + range.

- In **\_apply_markdown_at_search** and **\_find_text_ranges**: when we have plain text from LO (which uses `\n`), build **multiple literal candidates** by replacing `\n` with different break sequences: e.g. keep plain, and add `plain.replace("\n", "\n\n")`, `plain.replace("\n", "\r\n")`, `plain.replace("\n", "\r\n\r\n")`, and any other variants that might match Writer's storage. Try each with literal search (SearchRegularExpression = False).
- Keep or drop the single regex candidate as desired; the main fix is **trying more CR/LF variants** so multi-paragraph search can succeed.

## What was tried so far

- LO markdown-to-plain for the search string; one literal plain candidate + one line-break fuzzy regex candidate; hint when 0 replacements.
- Regex does not match across paragraphs in Writer. We previously had four literal variants (\n\n, \r\n, \r\n\r\n) and removed them in favor of the single regex; the fix is to **restore or extend** literal variants so we try different CR/LF types.

## Relevant files

- **markdown_support.py:** `_apply_markdown_at_search` (search_candidates), `_find_text_ranges` (plain + variants), hint when count==0 in `tool_apply_markdown`.
- **core/constants.py:** `DEFAULT_CHAT_SYSTEM_PROMPT` (optional: no need to push find_text + range for sections if search can be made to work).
- **Chat debug log:** `~/.config/libreoffice/4/user/config/localwriter_chat_debug.log` (or paths from `debug_log_paths`).

## Log reference

User query: "Convert my Summary Section to Finnish." apply_markdown(search= full section text) → 0 replacements (candidates: exact, plain, regex). find_text(same) → 0. Document prefix shows content like `Summary\nA legendary...symphony.\n\nSkills`. So we need a candidate that matches how Writer actually stores that (e.g. which of \n, \n\n, \r\n is between "Summary" and "A legendary", and at the end of the paragraph).
