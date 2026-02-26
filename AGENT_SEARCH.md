# Agent Search: Web Search with Browser Cookies

This document outlines research and a plan for adding **web search** capabilities to LocalWriter. The goal is to let the AI perform search requests on the user’s behalf using **browser cookies** so requests look like a normal logged-in user, avoiding anonymous-user blocks, CAPTCHAs, or stricter rate limits.

---

## 1. Purpose and scope

- **Purpose**: Add a search capability (e.g. a `web_search` tool for the Chat agent) that uses the user’s browser cookies so search requests appear as normal user traffic.
- **Browser requirement**: Support the **top 5–10 most popular FOSS (or widely used) browsers** at the same time. Chrome and Firefox are the two most common examples, but the actual requirement is to support as many of the leading FOSS-friendly browsers as we can in one go — not “Chrome + Firefox only.” When the same code path supports more (e.g. via yt-dlp’s existing list), we should expose them all in config/UI so users can pick their browser.

---

## 2. SQLite in Python

**`sqlite3` is part of the Python standard library** on all major OSes (Windows, macOS, Linux) in normal CPython builds — no `pip install` required. Cookie database reading (Firefox `cookies.sqlite`, Chrome/Chromium `Cookies`) uses only stdlib; no extra dependency for DB access. The only non-stdlib parts of cookie extraction are **decryption** (AES, and on Linux optional keyring via `secretstorage`).

---

## 3. yt-dlp cookie extraction (reference implementation)

### Location and scope

- **Source**: [yt-dlp/yt_dlp/cookies.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/cookies.py) (and related modules).
- **License**: Unlicense (public domain) — safe to copy and adapt.
- **Entry point**: `extract_cookies_from_browser(browser_name, profile=None, logger=..., keyring=None, container=None)` returns an `http.cookiejar.CookieJar` (yt-dlp uses a subclass `YoutubeDLCookieJar` extending `MozillaCookieJar`).

### Supported browsers (covers top FOSS browsers)

yt-dlp’s single implementation supports:

- **Chromium-based**: brave, chrome, chromium, edge, opera, vivaldi, whale.
- **Others**: firefox, safari.

That already covers the top 5–10 popular FOSS / widely used browsers. For LocalWriter we should **support all of these from day one** where the same code path applies: one browser dropdown (e.g. Chrome, Firefox, Chromium, Brave, Edge, Opera, Vivaldi, Whale, Safari) and shared extraction logic — no need to ship “Chrome + Firefox only” and add the rest later.

### Implementation details (yt-dlp)

- **Firefox**: Reads SQLite cookie DB (`cookies.sqlite`) from known profile paths. Schema version up to 17 supported; expiry can be in milliseconds (v16+). No OS-level decryption for cookie values. Multiple search roots (XDG, `~/.mozilla/firefox`, Flatpak, Snap). Optional container support via `containers.json`.
- **Chrome/Chromium (and other Chromium-based)**: Reads `Cookies` SQLite DB from the browser’s user data dir. Cookie **values** are often encrypted:
  - **Linux**: v10 (AES-CBC with fixed key `peanuts` or empty) or v11 (AES-CBC with key from **Secret Service / keyring**). Keyring name varies by browser (e.g. `Chrome`, `Chromium`). Optional dependency: `secretstorage` for v11.
  - **macOS**: v10 (AES-CBC, key from keyring, 1003 PBKDF2 iterations) or plaintext “old data.”
  - **Windows**: v10 (AES-GCM, key from DPAPI in “Local State”) or DPAPI-encrypted legacy.
- **Dependencies**: `sqlite3` (stdlib). Remaining: custom `yt_dlp.aes` (AES CBC/GCM, PKCS7 unpadding), `yt_dlp.dependencies` (optional `secretstorage` for Linux v11), and internal utils. No separate PyPI crypto package required if the small aes module is copied.

### Known issues (yt-dlp)

- **Chrome on Windows**: “Permission denied” when the cookie DB is locked (Chrome running). Workaround: close Chrome before extraction ([issue #7271](https://github.com/yt-dlp/yt-dlp/issues/7271)).
- **Firefox ESR / custom paths**: Only standard profile paths are searched; custom install paths may need an explicit profile path.
- **Linux keyring**: If keyring is unavailable or user denies access, v11 cookies may fail to decrypt; v10 may still work.

---

## 4. Using cookies in HTTP requests

- **Standard library**: `http.cookiejar.CookieJar` can attach cookies to a `urllib.request.Request` via `jar.add_cookie_header(request)`. The request then carries a `Cookie` header for the target URL’s domain/path.
- **LocalWriter today**: `core/api.py` uses `urllib.request.Request`, `sync_request()`, and `LlmClient` with `_headers()` (Content-Type, Authorization, Referer, X-Title). There is no cookie handling yet.
- **Integration**: A search client (separate from LlmClient) would (1) obtain a `CookieJar` from browser extraction, (2) build `urllib.request.Request(search_url)`, (3) call `jar.add_cookie_header(request)`, (4) use the same SSL/request pattern as `sync_request()` (or a small helper) to perform the GET. Cookie extraction is independent of the LLM API; only the **search** HTTP path needs the jar.

---

## 5. Options for cookie extraction in LocalWriter

| Approach | Effort | Pros | Cons |
|----------|--------|------|------|
| **A) Port minimal yt-dlp code** | High | No new dependency; full control; Unlicense; support all browsers yt-dlp supports | Must port `cookies.py`, `aes.py`, and minimal deps; platform-specific paths and keyring; ongoing maintenance for DB format changes |
| **B) Optional dependency on yt-dlp** | Low | Battle-tested; supports top 5–10 FOSS browsers in one go | Large dependency for one feature; thin wrappers for CLI/logger |
| **C) browser_cookie3** | Low | Lightweight; works with urllib | **LGPL-3.0**; mainly Chrome + Firefox; may lag behind encryption/format changes |

**Recommendation**: Document all three. Prefer **B** for fastest path (and to support the full browser set at once); **A** if the project must avoid heavy or GPL-family dependencies. **C** is a fallback if LGPL is acceptable but only covers a subset of the target browsers.

---

## 6. Search request shape and endpoints

- **Goal**: Perform a **GET** request to a search URL (e.g. query in query string), with **Cookie** and **User-Agent** (and optionally Referer) so the server sees a normal browser session.
- **Endpoints**: No single “official” API for “Google search as user.” Options:
  - **DuckDuckGo HTML**: e.g. `https://duckduckgo.com/html/?q=...` — often more permissive; can be scraped for result links/snippets.
  - **Google**: Direct GET to search URL is possible but subject to ToS and bot detection; cookies improve success rate but do not guarantee no CAPTCHA or blocking.
  - **Bing / others**: Similar to Google; configurable later.
- **Parsing**: For a first version, either (1) simple HTML scraping (e.g. links + snippets from one chosen engine) or (2) a configurable “search URL template” plus minimal parsing. No need for Google Custom Search API for the cookie-based “user-like” flow.

---

## 7. Integration points in LocalWriter

- **Tool**: New tool (e.g. `web_search`) in the same style as `core/document_tools.py`: schema in `WRITER_TOOLS` (or shared), implementation calling a small search module that (1) gets cookie jar from config-selected browser, (2) builds request with cookies, (3) GETs search URL, (4) parses and returns a structured result (e.g. list of `{title, url, snippet}`).
- **Config**: New keys in `core/config.py` and Settings UI: e.g. `search_browser` with options for **all supported browsers** (chrome, firefox, chromium, brave, edge, opera, vivaldi, whale, safari), optional `search_browser_profile`, and `search_engine` or `search_url_template`. Cookie extraction runs when the tool is invoked (or once per session with caching).
- **Prompt**: Extend `core/constants.py` system prompt to mention the `web_search` tool when enabled (e.g. “Use web_search to look up current information.”).

---

## 8. Effort and risks

**Effort**

- **Cookie extraction (port or use yt-dlp)**: Medium–high if porting (cookies.py + aes.py + minimal deps; optional secretstorage). Low if using yt-dlp as optional dependency: wrap `load_cookies(None, (browser, profile, keyring, container), ydl)` and use returned jar; supports top 5–10 browsers at once.
- **Search client**: Low — one module: query + cookie jar → GET with `add_cookie_header`, reuse existing SSL/request pattern, return parsed results.
- **Tool + config + UI**: Low–medium — one new tool, config keys, Settings dialog with **browser dropdown listing all supported browsers**.

**Risks and mitigations**

- **Chrome DB locked (Windows)**: Document “close Chrome” or choose another browser; optionally detect and show a clear error.
- **Keyring (Linux)**: Make `secretstorage` optional; degrade to v10-only or show a clear message if v11 decryption fails.
- **ToS / blocking**: Document that cookies are for “user-like” requests; prefer DuckDuckGo or configurable engine; do not claim Google approval.
- **Security**: Cookies are sensitive; read only when user enables search and selects a browser; do not log or send cookie values to the LLM; use jar only for the search request.

---

## 9. JavaScript and browser usage: yt-dlp vs. “run JS in Chrome”

### Does yt-dlp use a browser or a JS engine?

**Neither in the sense of a full browser.** yt-dlp splits two concerns:

- **Cookies**: Read from the **browser’s cookie database on disk** (Chrome’s `Cookies` SQLite, Firefox’s `cookies.sqlite`, etc.). No browser process is started; no JS is run. That’s the only part we need for “search with user cookies.”
- **JavaScript**: For sites that require JS (e.g. YouTube’s challenge scripts), yt-dlp uses **external JavaScript runtimes** — not a headless browser. It runs JS **outside** a browser via [EJS (External JavaScript for yt-dlp)](https://github.com/yt-dlp/yt-dlp/wiki/EJS): Deno (default), Node, Bun, or QuickJS. Scripts are executed by these runtimes; there is no Chrome/Firefox process. So yt-dlp has no built-in JS engine and does not use a browser for JS.

**Implication for Agent Search**: Our cookie-based search only needs the cookie-extraction path. We do not need yt-dlp’s JS/runtime path unless we later add something like “solve a challenge page” (and even then we could use an external runtime, not a browser).

### Easy way to “make requests + run JS” via Chrome (without Playwright)

**Playwright is a huge dependency** (Python package bundles a large Node.js binary, ~118 MB+; full browser automation stack). If we ever want to “use Chrome to load a page and run JS” (e.g. render a JS-heavy search result page, or run a snippet and return the result), we can avoid Playwright by using a **small CDP (Chrome DevTools Protocol) client** and the user’s **existing Chrome/Chromium**:

- **PyCDP** ([py-cdp.readthedocs.io](https://py-cdp.readthedocs.io/), [python-cdp](https://github.com/HMaker/python-cdp)): Thin Python client generated from the CDP spec. No bundled browser, no Node. You connect to a Chrome instance (launched with `--remote-debugging-port=...` or use an existing one), then send CDP commands (navigate, evaluate JS, get cookies, etc.). Dependency is “Chrome on the system” + this small library. The library is **code-generated and organized by CDP domains** (Browser, DOM, Page, etc.), so we can depend only on the modules we need. **We’d use PyCDP for the Chrome path and consider bundling it** (e.g. vendoring or shipping it with the extension) so the “run JS in Chrome” mode doesn’t require a separate pip install.
- **Pydoll**: Lightweight, CDP-based, async; alternative if we prefer a different API.
- **pyppeteer**: Python port of Puppeteer; launches Chromium and uses CDP. Lighter than Playwright but still “browser automation” rather than “minimal client.”

### Lightweight option for Firefox

Firefox does **not** use CDP long-term: **CDP support in Firefox is deprecated as of Firefox 129** in favor of **WebDriver BiDi**. So for Firefox we need a different lightweight path:

- **Marionette**: Firefox’s built-in remote protocol. The **server runs inside the Firefox binary**; you start Firefox with `-marionette` (default port **2828**). Communication is **JSON over TCP** (no HTTP). Commands are WebDriver-style (e.g. `WebDriver:Navigate`, `WebDriver:GetTitle`). No separate “geckodriver” binary is required if we launch Firefox ourselves and connect to the socket. Documentation: [Marionette Protocol (MDN)](https://developer.mozilla.org/en-US/docs/Mozilla/QA/Marionette/Protocol), [Firefox Source Docs](https://firefox-source-docs.mozilla.org/testing/marionette/Protocol.html).
- **Python clients for Marionette**: Two options:
  - **[k0s/marionette_client](https://github.com/k0s/marionette_client)**: Tiny, sync, easy to vendor — but **last updated ~15 years ago**. The Marionette protocol has since evolved (protocol levels 2/3, W3C WebDriver alignment, message indexing). We could **vendor and minimally adapt** it for a narrow use (connect, navigate, execute script); it might still work for current Firefox for that subset, but there’s risk of subtle breakage or missing commands. Use with caution.
  - **Mozilla’s maintained client**: The PyPI package `marionette_client` is [inactive and superseded by **marionette-harness**](https://pypi.org/project/marionette_client/); the actual Python client library is **`marionette_driver`** (from Mozilla’s [testing/marionette/client](https://firefox-source-docs.mozilla.org/testing/marionette/Testing.html)). So the **maintained** option is to depend on `marionette_driver` (or vendor the client from mozilla-central). It’s larger than k0s’s tiny client but kept in sync with the protocol.
- **WebDriver BiDi**: The intended replacement for CDP in Firefox; WebSocket-based. Selenium 4 supports it (`enable_bidi=True`). For a minimal stack we could use a small BiDi client instead of full Selenium, but Marionette is simpler and already “just TCP + JSON.”

**Summary**: For **Chrome/Chromium** we’d use **PyCDP** (and consider bundling it). For **Firefox**: either **vendor k0s/marionette_client** knowing it’s old and we may need to fix protocol compatibility, or use the **maintained `marionette_driver`** (dependency or vendor from mozilla-central) for a supported path. Both avoid Playwright.

**Practical split for LocalWriter**:

1. **Phase 1 (search with cookies)**: Cookie extraction (yt-dlp-style or optional yt-dlp) + plain HTTP GET with `Cookie` header. **No browser, no JS execution.** Covers “search as the user” with minimal deps.
2. **Optional later**: If we need “load this URL and run JS / get rendered content”:
   - **Chrome/Chromium**: Optional path using **PyCDP** (use it, consider bundling) and the user’s Chrome with `--remote-debugging-port`.
   - **Firefox**: Optional path using a Marionette client (vendor k0s/marionette_client at our own risk, or use maintained `marionette_driver`) and Firefox with `-marionette`. Keep optional so the core search path stays dependency-light.

---

## 10. References

- yt-dlp cookies module: <https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/cookies.py>
- Chrome cookie decryption (os_crypt): <https://chromium.googlesource.com/chromium/src/+/HEAD/components/os_crypt/>
- Linux keyring (Chromium): <https://chromium.googlesource.com/chromium/src/+/HEAD/components/os_crypt/sync/key_storage_linux.cc>
- yt-dlp FAQ (cookies-from-browser): <https://github.com/yt-dlp/yt-dlp/wiki/FAQ>
- browser_cookie3 (alternative, LGPL): <https://github.com/borisbabic/browser_cookie3>
- sqlite-vec (vector extension; not stdlib): <https://github.com/asg017/sqlite-vec>
- yt-dlp EJS (external JS runtimes, no browser): <https://github.com/yt-dlp/yt-dlp/wiki/EJS>
- PyCDP (lightweight CDP client; use for Chrome, consider bundling): <https://py-cdp.readthedocs.io/>, <https://github.com/HMaker/python-cdp>
- Pydoll (lightweight CDP-based automation): <https://github.com/thalissonvs/pydoll>
- Playwright Python size (Node binary): <https://github.com/microsoft/playwright-python/issues/2688>
- Firefox Marionette protocol: <https://developer.mozilla.org/en-US/docs/Mozilla/QA/Marionette/Protocol>, <https://firefox-source-docs.mozilla.org/testing/marionette/Protocol.html>
- Firefox CDP deprecated (129+), BiDi: <https://fxdx.dev/deprecating-cdp-support-in-firefox-embracing-the-future-with-webdriver-bidi>
- k0s/marionette_client (tiny, ~15 years old; vendor at own risk): <https://github.com/k0s/marionette_client>
- marionette_driver (Mozilla’s maintained Marionette Python client): PyPI `marionette_driver`, Firefox source [testing/marionette](https://firefox-source-docs.mozilla.org/testing/marionette/Testing.html)
