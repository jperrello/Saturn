# cbt.2.c.timeout — per-call MCP deadline via `asyncio.wait_for`

**Bead:** Saturn-ex3   **Commit:** `83633d3`

`MCPClientManager.call()` previously inherited the
`streamablehttp_client` defaults (`sse_read_timeout=300`), so a hung
tool blocked the caller for ~5 minutes — long enough that the chat UI
looked indistinguishable from a frozen Saturn web.

Fix: wrap the invoke step with
`asyncio.wait_for(..., timeout=CALL_DEADLINE_S)`. On timeout, return
the same shape the unreachable-server fix uses (`{"error":
"MCP tool '<n>' timed out after Ns"}`) so the chat surface presents a
single, readable failure mode for both classes.

## Reproducer (real fake-MCP fixture, no mocks of the timeout itself)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_mcp_timeout_ex3.py
```

The `@pytest.mark.fake_mcp(hang=30.0)` fixture spins a real MCP server
that sleeps for 30 seconds inside the tool handler; the test asserts
the `call()` returns within 10 seconds with a timeout error string.

## Captured output

```text
saturn/tests/test_mcp_timeout_ex3.py::test_hung_tool_call_aborts_within_10s PASSED
========================= 1 passed in <Ns> ============================
```

## Why this matters

This closes the second of three MCP failure modes from cbt.2.c:

  - **unreachable** (Saturn-c4n / `5ac0a28`) — server down → human-readable error
  - **timeout**     (Saturn-ex3 / `83633d3`) — server hangs   → human-readable error  ← this bead
  - **oversized**   (Saturn-eic / `4961da8`) — server returns a 10 MiB blob → hard reject

Together they reduce the three "MCP looks broken" symptoms to a single,
shaped error that the model and user can both read.
