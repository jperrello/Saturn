# cbt.cross-client — `/v1/*` contract across HTTP stacks

**Bead:** Saturn-ggn   **Status:** GREEN-on-arrival regression guard
(no implementation commit).

Phase-3 API guarantee. Every `/v1/*` endpoint MUST return semantically
identical responses regardless of which HTTP client the caller uses.
The contract pins the invariant against three distinct stacks:

  1. Python `urllib`     (stdlib)
  2. Python `httpx`      (async-native, Saturn's own client)
  3. subprocess `curl`   (libcurl-based reference)

Go (`net/http`) is deferred — no Go test harness in this repo;
**Saturn-ggn.go** would file when one lands.

## Endpoints exercised

  - `GET  /v1/health`
  - `GET  /v1/models`
  - `POST /v1/chat/completions` (non-streaming)
  - `POST /v1/chat/completions` (streaming SSE)

The oracle compares a *canonical* extracted form per endpoint, not raw
bytes — fields like `created` (unix timestamp) and `id` (per-call
uuid) naturally vary even within one client across calls. The
canonical forms strip those before diffing.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_cross_client_ggn.py
```

## Captured output

```text
saturn/tests/test_cross_client_ggn.py::
test_cross_client_v1_endpoints_return_identical_canonical_forms PASSED    [100%]
========================= 1 passed in <Ns> ============================
```

## Why this matters

The whole "OpenAI-compatible" pitch falls over the moment a client
sees a different shape than another client. ggn pins the invariant
*before* the next contributor's middleware change introduces a
subtle Content-Type drift only `httpx` happens to swallow.
