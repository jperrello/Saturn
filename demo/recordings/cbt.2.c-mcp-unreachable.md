# cbt.2.c — MCP unreachable error is human-readable

**Bead:** Saturn-c4n (cbt.2.c sub-bead "MCP server unreachable").
**Commit:** `5ac0a28`.   **Brutus contract:** `.brutus/Saturn-c4n/CONTRACT.md`.

Two open siblings still in_progress under cbt.2.c: **Saturn-ex3** (tool-call
timeout edge) and **Saturn-eic** (oversized tool result edge).

## What ships

`saturn/mcp_client.py::MCPClientManager.call()` previously surfaced anyio's
bare `'unhandled errors in a TaskGroup (1 sub-exception)'` to the chat UI
when the configured MCP server was unreachable. Wrapped with a small
`_unwrap()` helper that walks `BaseExceptionGroup` chains, matches
`ConnectionError` / `OSError` at the leaf, and returns:

```json
{"error": "MCP server '<name>' unreachable at <url>: <inner>"}
```

The user gets a sentence that names the failing server and the underlying
socket error. The chat surface treats the dict as a tool-call error and
lets the model see it.

## Reproducer (no mocks — real closed TCP port)

```sh
$ PY="$(head -1 "$(command -v saturn)" | sed 's|^#!||')"
$ "$PY" -m pytest -xvs saturn/tests/test_mcp_edges_cbt2c.py
```

## Captured output

```text
collected 1 item

saturn/tests/test_mcp_edges_cbt2c.py::
test_unreachable_mcp_call_returns_human_error PASSED

========================= 1 passed, 2 warnings in 1.47s =========================
```

The test reserves a free port, immediately closes the listener, registers
that closed-port URL as an MCP server, and invokes a tool. The asserted
error string contains both the server name and the connection-refused
phrasing.

## Why this matters

MCP is the "bring your own tools" surface. When a configured tool server is
down (typo'd URL, container crashed, network blip) the user must be able
to read the error and fix it without grep'ing the model's transcript for
"TaskGroup". cbt.2.c.unreachable is the smallest of three MCP edges; the
two siblings (timeout / oversized result) come next.
