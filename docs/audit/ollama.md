# Ollama

First-party Saturn provider that proxies a local Ollama daemon
(`http://localhost:11434`) behind Saturn's OpenAI-compatible surface.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Source: `saturn/servers/ollama.py`. Service definition:
`saturn/services/ollama.toml`.

```toml
# saturn/services/ollama.toml
name       = "ollama"
deployment = "local"
api_type   = "ollama"
priority   = 50

[upstream]
base_url = "http://localhost:11434/v1"

[server]
port   = 0           # auto-allocated
module = "saturn.servers.ollama"

[beacon]
enabled = false
```

Upstream contract: a running Ollama daemon reachable at
`http://localhost:11434` (`saturn/servers/ollama.py:13`,
`OLLAMA_BASE_URL = "http://localhost:11434"`). Saturn provides the
OpenAI-compatible front; Ollama provides the model.

## How it points at Saturn

The Saturn launcher reads `ollama.toml`, starts the FastAPI app at
`saturn/servers/ollama.py:15` on an auto-allocated port (`port = 0`), and
registers under `_saturn._tcp.local.` with `priority=50`, `api_type=ollama`,
`deployment=local`.

Endpoints exposed (`saturn/servers/ollama.py:23, :34, :51`):

| Path | Method | Behaviour |
|---|---|---|
| `/v1/health` | GET | Probes Ollama `/api/version` (2 s timeout). 503 if unreachable. |
| `/v1/models` | GET | Translates Ollama `/api/tags` to OpenAI `{ object: "model", owned_by: "ollama" }`. 503 on failure. |
| `/v1/chat/completions` | POST | Forwards to Ollama `/api/chat` with `(connect=10s, read=None)` timeout; passes `tools`; surfaces `tool_calls`. Streams SSE chunks. |

Streaming pipeline (`saturn/servers/ollama.py:78–123`): line-delimited
JSON from Ollama → `chunk()` envelopes → `data: …\n\n`; emits a `[DONE]`
sentinel and propagates `finish_reason="tool_calls"` when tool calls were
seen.

Non-streaming response (`saturn/servers/ollama.py:125–146`) maps
`prompt_eval_count` / `eval_count` into OpenAI `usage.prompt_tokens` /
`usage.completion_tokens`.

## Known issues

- **Hard-coded localhost.** `OLLAMA_BASE_URL` is a module-level constant
  (`saturn/servers/ollama.py:13`). Cannot be overridden by env var;
  multi-host deployments require editing the source.
- **TOML drift between `[upstream]` and the module.** `ollama.toml` declares
  `base_url = "http://localhost:11434/v1"` (with `/v1`); the module hits
  `http://localhost:11434/api/version`, `/api/tags`, `/api/chat`
  (no `/v1`). The TOML value is never consulted by the module — it is
  metadata for the advertiser, not configuration for the proxy.
  [needs-research] whether any consumer reads `[upstream].base_url`
  meaningfully.
- **Stream cleanup.** `response.close()` runs in a `finally`
  (`saturn/servers/ollama.py:120–121`); upstream errors during streaming
  raise, the SSE channel terminates without a `[DONE]` sentinel, and the
  client must observe the connection close.

## Test
See `tests/integrations/test_ollama.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
