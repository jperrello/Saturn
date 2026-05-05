# CONTRACT — Saturn-ggn / cbt.cross-client: `/v1/*` HTTP-stack parity

**Status:** GREEN on first run. **Regression-guard contract.**
**Implementer:** none required.

## Spec restatement (falsifiable)

Every Saturn `/v1/*` endpoint MUST return semantically identical responses
regardless of HTTP client. Three real stacks exercised against a real
`ServiceRunner` subprocess (Ollama upstream):

  - Python `urllib` (stdlib)
  - Python `httpx` (Saturn's own client)
  - subprocess `curl` (libcurl reference)

Endpoints:

  - `GET /v1/health`
  - `GET /v1/models`
  - `POST /v1/chat/completions` (non-streaming)
  - `POST /v1/chat/completions` (streaming SSE)

Per-endpoint comparison uses a *canonical extracted form* — fields like
`created` (timestamp) and `id` (per-call uuid) naturally vary even within
one client across calls and are stripped from the comparison.

Go (`net/http`) deferred — no Go test harness. File **Saturn-ggn.go** if
one lands.

## Test files

- `saturn/tests/test_cross_client_ggn.py` (added; 1 test, 4 sub-comparisons).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_cross_client_ggn.py --no-header -rN --tb=short
```

Requires Ollama running with `qwen2.5:0.5b`.

## Captured first-run output

```
========================= 1 passed, 1 warning in 2.47s =========================
```

Three clients × four endpoints all yielded identical canonical forms.
Transcript: `.brutus/Saturn-ggn/transcript.md`.

## Why no red phase

The runner's `/v1/*` endpoints are spec-compliant FastAPI handlers
returning either JSON (`/v1/health`, `/v1/models`, non-streaming chat) or
text/event-stream (streaming chat). All three HTTP stacks read the same
bytes off the wire and parse them identically. There is no missing
behavior to gate. House rules allow regression-guard contracts; this
contract pins the parity so a future refactor (e.g., custom
content-encoding, non-standard SSE framing) cannot silently break a
caller using a different stack.

## Oracle definition

| Endpoint | Canonical form |
|---|---|
| `/v1/health` | `{status, saturn, deployment, api_type}` subset |
| `/v1/models` | sorted list of model `id` strings |
| `chat non-stream` | `{model, finish_reason, role, content_present}` |
| `chat stream` | reconstructed `{model, finish_reason, content_present}` from SSE deltas |

For each endpoint, the test asserts `len(set(canonical_forms)) == 1`
across the three clients.

## Out of scope

- Go (`net/http`) parity — **Saturn-ggn.go** when a Go test harness lands.
- Raw byte-equality — timestamps and ids vary per call; canonical
  comparison is the meaningful invariant.
- Additional clients (Rust `reqwest`, JavaScript `fetch`, etc.) — file
  per-stack sub-beads if needed.
- Web-UI (`/api/*`) cross-client parity — different surface; file as
  **Saturn-ggn.api** if needed (less interesting since the only consumer
  is the bundled Web-UI).
- Authentication-error parity (401 with WWW-Authenticate, etc.) — already
  covered by `saturn/tests/test_runner_auth.py`.

## Implementer

None. Brutus attests the regression guard. Athena: file Saturn-ggn.go
when a Go harness is available.

## Transcript

`.brutus/Saturn-ggn/transcript.md`
