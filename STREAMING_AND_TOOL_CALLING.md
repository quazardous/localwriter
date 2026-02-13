# Streaming and Tool Calling: How the APIs Work

This document explains how OpenAI-compatible chat APIs handle **streaming** and **tool calling**, and how **reasoning/thinking** appears in streams. It is aimed at developers who need to implement or debug clients (e.g. LocalWriter’s chat sidebar).

References: OpenAI [Streaming](https://platform.openai.com/docs/api-reference/streaming), [Tool calling](https://platform.openai.com/docs/guides/function-calling); OpenRouter [Streaming](https://openrouter.ai/docs/api-reference/streaming), [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

---

## 1. Chat completions: streaming (no tools)

**Request:** Same URL, `stream: true`.

**Response:** HTTP body is **Server-Sent Events (SSE)**. Each event is a line starting with `data: `. The payload is JSON. Last event is usually `data: [DONE]`.

**Chunk shape (content-only):**

```json
{
  "id": "chatcmpl-...",
  "choices": [
    {
      "index": 0,
      "delta": { "content": "The ", "role": "assistant" },
      "finish_reason": null
    }
  ]
}
```

Later chunks may have only new content:

```json
{ "choices": [{ "delta": { "content": "capital" }, "finish_reason": null }] }
```

Final chunk:

```json
{ "choices": [{ "delta": {}, "finish_reason": "stop" }] }
```

**Client behavior:**

- Read line by line; skip empty lines and comments (e.g. OpenRouter sends `: OPENROUTER PROCESSING`).
- If line is `data: [DONE]`, stop.
- Otherwise parse `data: <json>`. From `choices[0].delta` take:
  - `content` — append to the displayed reply.
  - `finish_reason` — when non-null, stream is done (and may be `stop`, `length`, etc.).

The **delta** only contains what **changed** in this chunk; the client accumulates content itself.

---

## 2. Streaming when tools are in the request

When you send `stream: true` **and** `tools` in the request, the API can still return a stream, but the **delta** now includes **partial tool call** data. The client must **accumulate** these deltas into a full message before it can run tools.

**Chunk shape (streaming with tool_calls):**

- Early chunks may contain **reasoning/thinking** (see section 3) and/or **content** deltas.
- Chunks for tool calls look like:

```json
{
  "choices": [{
    "delta": {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        { "index": 0, "id": "call_abc", "type": "function", "function": { "name": "get_weather", "arguments": "" } }
      ]
    },
    "finish_reason": null
  }
}
```

Later chunks add **partial arguments** (only the new fragment):

```json
{
  "choices": [{
    "delta": {
      "tool_calls": [
        { "index": 0, "function": { "arguments": "{\"location\":" } }
      ]
    }
  }
}
```

```json
{
  "choices": [{
    "delta": {
      "tool_calls": [
        { "index": 0, "function": { "arguments": " \"Paris\"}" } }
      ]
    }
  }
}
```

So **one** tool call is spread across **many** chunks. The client must:

- Maintain a buffer per `index` (or `id` when present): `id`, `type`, `function.name`, `function.arguments`.
- For each chunk, **merge** `delta.tool_calls[i]` into the buffer for that index (e.g. append `function.arguments`).
- When the stream ends (`finish_reason` set or `[DONE]`), parse the accumulated `function.arguments` as JSON and run the tools.

Order of appearance in the stream is typically: optional reasoning deltas, optional content deltas, then tool_calls deltas (often after content/reasoning). The exact order is provider-dependent.

---

## 3. Reasoning / thinking in the stream

Some models (e.g. OpenRouter with Claude, Gemini, or reasoning models) send **reasoning** or **thinking** tokens in addition to the main reply. These appear in the **same** SSE stream, in the **delta**.

### 3.1 OpenRouter-style: `reasoning_details`

OpenRouter normalizes reasoning into **reasoning_details**. In **streaming** responses, each chunk may contain:

- `choices[0].delta.reasoning_details`: **array** of objects. Each object can be:
  - `type: "reasoning.text"` and `text`: string to show as thinking.
  - `type: "reasoning.summary"` and `summary`: string summary.
  - `type: "reasoning.encrypted"` and `data`: opaque (e.g. redacted).

So the client should:

- For each chunk, read `delta.reasoning_details` (if present).
- For each element, if `type === "reasoning.text"` append `text`; if `type === "reasoning.summary"` append `summary` (or treat similarly).
- Pass that concatenated string to the UI (e.g. “thinking” area or same box as content).

Reasoning chunks often **precede** content chunks; the model “thinks” then “replies”. So in the same stream you may see:

1. Several chunks with only `delta.reasoning_details`.
2. Then chunks with `delta.content`.
3. Optionally chunks with `delta.tool_calls`.

### 3.2 Other providers: `reasoning_content`

Some APIs use a single string field in the delta, e.g. `delta.reasoning_content`. Same idea: if present, append it to the thinking buffer and show it in the UI.

---

## 4. Summary table

| Mode                   | Request                  | Response   | Content              | Tool calls                        | Reasoning / thinking  |
|------------------------|--------------------------|------------|----------------------|-----------------------------------|------------------------|
| Chat, stream           | `stream: true`           | SSE chunks | `delta.content`      | N/A (no tools)                    | `delta.reasoning_*`    |
| Chat + tools, stream   | `stream: true`, `tools`  | SSE chunks | `delta.content`      | `delta.tool_calls` (accumulate)   | `delta.reasoning_*`    |

\* When the API supports it and the model returns it.

---

## 5. Testing with OpenRouter

If you have an OpenRouter API key, you can verify how streaming, tool calls, and reasoning actually behave.

### 5.1 What to test

1. **Streaming without tools**
   - `POST https://openrouter.ai/api/v1/chat/completions`, `stream: true`, no `tools`.
   - Inspect each SSE chunk: `choices[0].delta.content`, `finish_reason`. Confirm content is incremental and `[DONE]` or final chunk ends the stream.

2. **Streaming with a reasoning model**
   - Same URL, `stream: true`, use a model that returns reasoning (e.g. one of the OpenRouter models listed in their [reasoning docs](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)). Optionally set `reasoning: { effort: "low" }` in the body (OpenRouter-specific).
   - Inspect chunks for `choices[0].delta.reasoning_details`: you should see arrays of `{ type: "reasoning.text", text: "..." }` (or similar) before or interleaved with `delta.content`.

3. **Streaming with tools**
   - Same URL, `stream: true`, add a minimal `tools` array (e.g. one function) and ask the model to call it.
   - Inspect chunks for `delta.tool_calls`: first chunk(s) may have `id`, `type`, `function.name`, `arguments: ""`; later chunks add fragments to `function.arguments`. Confirm you can concatenate `arguments` and parse as JSON.

4. **Streaming with tools + reasoning**
   - Combine (2) and (3): model that supports reasoning, with tools. You should see reasoning_details chunks, then content and/or tool_calls. Order and exact shape depend on the model; the doc above is the generic pattern.

### 5.2 What you’ll learn

- **Exact chunk order** for your chosen model (reasoning → content → tool_calls, or interleaved).
- **Exact field names** OpenRouter uses (`reasoning_details` vs any variant).
- **Whether** `function.arguments` is split across many small chunks or fewer larger ones (affects accumulation logic).
- **Whether** `finish_reason` is `"tool_calls"` when the model stops to call tools, and what the final chunk looks like.

### 5.3 How to run tests

- **Manual:** Use `curl` or a small script: set `Authorization: Bearer <OPENROUTER_API_KEY>`, `Content-Type: application/json`, body with `model`, `messages`, `stream: true`, and optionally `tools` and `reasoning`. Parse SSE line by line and log each chunk (or key fields).
- **In LocalWriter:** After implementing the streaming + thinking callback, point the extension at OpenRouter (endpoint `https://openrouter.ai/api/v1`, API key set) and use a reasoning model; observe the sidebar to see when thinking vs content appears.

Once you’ve run these tests, you can document the **actual** chunk shapes and order in this file or in a short “OpenRouter streaming notes” section so the implementation can be aligned with real responses.

---

## 6. Existing implementations: piecing streams together and firing tool calls

You don't have to hand-roll accumulation. These options already do the job.

### 6.1 OpenAI Python SDK (recommended if you can add a dependency)

The **[openai](https://pypi.org/project/openai/) package** implements streaming with tool-call accumulation and exposes a state object you can feed chunks into.

- **Stream API:** Use the client with `stream=True` and iterate; the stream yields parsed chunks and the library can give you a final completion with full `message.content` and `message.tool_calls` once the stream is done.
- **Manual chunk feeding:** If you already have SSE (e.g. from `urllib`), you can use the SDK's accumulation logic by building their chunk type from each JSON payload and calling the state handler.

**Relevant code:**

- **[`openai.lib.streaming.chat._completions`](https://github.com/openai/openai-python/blob/main/src/openai/lib/streaming/chat/_completions.py)**  
  - `ChatCompletionStreamState`: call `handle_chunk(chunk)` for each `ChatCompletionChunk`; when the stream ends, `get_final_completion()` returns a `ParsedChatCompletion` with `choices[0].message.content` and `choices[0].message.tool_calls` ready to execute.
  - The docstring shows standalone use: create a state, loop over your stream, call `state.handle_chunk(chunk)` each time, then `state.get_final_completion()`.
- **[`openai.lib.streaming._deltas`](https://github.com/openai/openai-python/blob/main/src/openai/lib/streaming/_deltas.py)**  
  - `accumulate_delta(acc, delta)`: generic merge of a delta into an accumulated dict. For `tool_calls`, it uses each item's `index`, finds the same index in the accumulator, and recursively merges (so `function.arguments` strings are concatenated). This is the core logic that "pieces it all together."

**Using the client with OpenRouter (or any OpenAI-compatible endpoint):**

```python
from openai import OpenAI

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key="...")
stream = client.chat.completions.create(
    model="...",
    messages=[...],
    tools=[...],
    tool_choice="auto",
    stream=True,
)
# Option A: use the stream context manager and get the final completion
with stream as s:
    for event in s:
        # e.g. content.delta, tool_calls.function.arguments.delta
        ...
    completion = s.get_final_completion()
# completion.choices[0].message has .content and .tool_calls — run tools, append tool results, repeat
```

So: use the SDK's stream, consume it until done, then call `get_final_completion()` and fire off the tool calls from `message.tool_calls`.

### 6.2 Dependency-free: reuse the accumulation algorithm

If you must avoid the `openai` dependency (e.g. LibreOffice extension with minimal deps), you can reuse the same **algorithm** as the SDK:

1. **Accumulate deltas:** Implement or copy **[`accumulate_delta`](https://github.com/openai/openai-python/blob/main/src/openai/lib/streaming/_deltas.py)** (plain dicts in, dicts out). Rules: same key → merge; for lists of objects use `index` to find the element and merge recursively; for strings, concatenate.
2. **Initial snapshot:** From the first chunk, build an initial "message" snapshot (e.g. `role`, empty `content`, empty `tool_calls` list).
3. **Loop:** For each subsequent chunk, `accumulate_delta(snapshot["choices"][0]["message"], chunk["choices"][0]["delta"])` (adjust keys to match the API; the delta often lives under `choices[0].delta`). After each merge, you can emit `delta.content` or `delta.reasoning_details` to the UI.
4. **When the stream ends** (`finish_reason` set or `data: [DONE]`): the snapshot's `message.tool_calls` is complete. Parse each `function.arguments` as JSON, run your tools, append tool results to `messages`, and send the next request (again with `stream=True` if you want streaming for the next round).

So "piece it all together" = one accumulated message state per stream; "fire off the tool calls when complete" = when the stream ends, read `message.tool_calls`, execute each, then continue the conversation loop.

### 6.3 OpenRouter Python SDK

If you only target OpenRouter, their **[Python SDK](https://openrouter.ai/docs/sdks/python)** supports chat with `stream=True` and handles responses. Check their [chat API reference](https://openrouter.ai/docs/sdks/python/api-reference/chat) for the exact stream shape and whether they expose a final message with `tool_calls` after the stream (similar to the OpenAI client).

### 6.4 Lightweight / FOSS-friendly: minimal deps, no full OpenAI SDK

The full **openai** package is a large dependency. If you want to stay minimal and widely compatible with FOSS setups (Ollama, local servers, OpenRouter), you have two practical options.

**Option A: Vendor the accumulation algorithm (zero new dependencies)**

There is no widely used, small, OpenAI-compatible library that does streaming + tool-call accumulation in one place besides the official SDK. The **lightweight approach** that many FOSS projects use is to **copy the accumulation logic** and keep your existing HTTP (e.g. `urllib` or `httpx`):

- **[`openai.lib.streaming._deltas.accumulate_delta`](https://github.com/openai/openai-python/blob/main/src/openai/lib/streaming/_deltas.py)** is ~60 lines, pure Python, no SDK imports in the function itself. It operates on plain dicts: you pass the accumulated message and the chunk’s `delta`, and it merges (strings concatenate, lists of objects merge by `index`). You can copy this function into your codebase (same license as your project; OpenAI’s repo is Apache 2.0). Then your loop is: parse SSE → build `delta` dict from `choices[0].delta` → `accumulate_delta(snapshot, delta)` → when stream ends, read `tool_calls` and run tools. **No new package required.**

**Option B: ollama-python (Ollama-native only)**

**[ollama-python](https://github.com/ollama/ollama-python)** is small (deps: `httpx`, `pydantic`), MIT-licensed, and very popular with FOSS/Ollama users. It talks to **Ollama’s native API** (e.g. `POST /api/chat`), not the OpenAI-compatible `/v1/chat/completions` endpoint. So it is not a drop-in for code that must work with OpenRouter, OpenAI, or “any OpenAI-compatible endpoint.” If you only ever call a local Ollama and are fine using its native API, ollama-python is a good lightweight client; when streaming with tools, you still have to **accumulate** partial `tool_calls` from chunks yourself (the library does not do that). Ollama also exposes an [OpenAI-compatible API](https://docs.ollama.com/openai) at `http://localhost:11434/v1/`; for that endpoint you’d use an OpenAI-compatible client (e.g. the full SDK or your own urllib + vendored `accumulate_delta`), not ollama-python’s native client.

**Summary:** For “small dependency, works with any OpenAI-compatible endpoint (Ollama compat mode, OpenRouter, etc.) and streams + tool calls,” the practical FOSS-friendly approach is **Option A**: keep your current HTTP, copy `accumulate_delta`, and do the small accumulation loop yourself. The full OpenAI SDK remains the only ready-made implementation that does everything in one place.
