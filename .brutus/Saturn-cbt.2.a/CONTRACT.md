# CONTRACT — Saturn-cbt.2.a: long-message HTTP regression guard

**Status:** GREEN on first run. **This is a regression-guard contract**, not a
red→green new-behavior contract. House rules allow this when "the change is
meant to preserve behavior, the contract is that the existing test suite still
passes — verify it."

**Implementer:** none required for the HTTP layer (already works). Athena
should file **cbt.2.a.ui** as a sibling for the actual UI-freeze proof, route
to a UI/Playwright crew member (forge or whoever drives bombadil .ts).

## Decomposition note

cbt.2 was a 4-feature laundry list. Brutus refused to bundle. Decomposed:

- **cbt.2.a** — long messages (this contract)
- **cbt.2.b** — attachments via `+` menu
- **cbt.2.c** — MCP edges (server unreachable, tool timeout, oversized result)
- **cbt.2.d** — edit-and-regenerate flake

Each gets its own brutus contract when reached. Do not bundle.

## Spec restatement (falsifiable)

Sending a `>4k-token` user message (≥16 000 characters) to `POST /api/chat`
MUST satisfy:

1. The response is HTTP 200 streaming SSE.
2. **Time-to-first SSE data line < 5s.** This is the HTTP-side proxy for
   "UI doesn't freeze" — a freeze symptom in the browser is caused by the
   server buffering the entire upstream response before flushing. If saturn
   web streams promptly, the UI gets chunks to render.
3. The final SSE chunk before `[DONE]` carries `saturn_meta` with
   `schema_version=1`, `applied.usage.prompt_tokens >= 1000` (proves the
   large input reached the upstream), and `configured.model` echoes the
   request.

## Test files

- `saturn/tests/test_long_messages_cbt2a.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_long_messages_cbt2a.py --no-header -rN --tb=line
========================= 1 passed, 1 warning in 3.47s =========================
```

Requires Ollama running at `http://localhost:11434/v1` with `qwen2.5:0.5b`.

## Captured first-run output (verbatim)

```
saturn/tests/test_long_messages_cbt2a.py .                               [100%]
========================= 1 passed, 1 warning in 3.47s =========================
```

Full transcript: `.brutus/Saturn-cbt.2.a/transcript.md`.

## Why no red phase

Brutus attempted to author a new-behavior failing test for "UI doesn't freeze
under long messages." The HTTP path through `/api/chat` already streams
without server-side buffering; the qj5.15 receipt is already correctly
emitted under load. There is no missing behavior at the HTTP layer to gate.

Further tightening (e.g. TTFB < 0.8s) would create a flaky test gated on
Ollama's own latency, not on saturn behavior — that's not a meaningful red.

The TRUE UI-freeze proof requires a browser running the chat UI, measuring
input-event handling latency and repaint cadence while a long stream is
in-flight. That is a Playwright/Bombadil concern. **Filed as cbt.2.a.ui**.

## Oracle definition (regression invariant)

| Field | Oracle |
|---|---|
| Response status | 200 |
| TTFB (first SSE `data:` line with content) | < 5s |
| `saturn_meta.schema_version` | == 1 |
| `saturn_meta.applied.usage.prompt_tokens` | >= 1000 |
| `saturn_meta.configured.model` | == requested model |

## Out of scope

- 32k-token (>128 000 chars) case: qwen2.5:0.5b context window cannot ingest
  that much input. Testing that path requires either a larger-context local
  model OR an OpenRouter sub-key with a long-context model. Filed as
  cbt.2.a.long32k follow-up if needed.
- Browser-side freeze detection (Bombadil/Playwright). → cbt.2.a.ui.
- Attachments, MCP, edit-regen → cbt.2.b/c/d.
- Performance budget tightening below 5s TTFB.

## Implementer

None for the HTTP layer. Brutus attests the regression guard is in place.
Athena: file cbt.2.a.ui and route to a UI crew member for the real test.

## Transcript

`.brutus/Saturn-cbt.2.a/transcript.md`
