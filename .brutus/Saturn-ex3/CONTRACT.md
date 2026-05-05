# CONTRACT — Saturn-ex3 / cbt.2.c.timeout: MCP tool-call timeout enforcement

**Status:** RED. 1 test pinned.
**Implementer:** athena will route (recommended: hardener — wrap `MCPClientManager.call` with `asyncio.wait_for` deadline, or pass tighter `sse_read_timeout` into `streamablehttp_client`).

## Spec restatement (falsifiable)

`saturn/mcp_client.py:69-80`'s `MCPClientManager.call()` currently relies on
`streamablehttp_client`'s defaults (`timeout=30, sse_read_timeout=300`). When
an MCP server accepts a connection but the tool itself hangs (e.g., an
infinite loop or blocking I/O inside the tool body), the client blocks for
up to ~5 minutes before any error reaches the caller.

The fix MUST guarantee: when an MCP tool stalls, `call(...)` returns within
**10s wall clock** with a `dict` whose `"error"` field mentions
"timeout" / "timed out" / "deadline" / "exceeded" / "cancel".

The exact deadline value is the implementer's choice; 10s is the test's
upper bound. A 5s deadline in the implementation would still pass the
oracle.

## Test files

- `saturn/tests/test_mcp_timeout_ex3.py` (added; 1 test).
- `saturn/tests/conftest_mcp.py` (added; shared fake-MCP fixture, also
  consumed by Saturn-eic / cbt.2.c.large).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_mcp_timeout_ex3.py --no-header -rN --tb=short
```

No external dependency. Spawns `mcp.server.FastMCP` (already in deps) as a
subprocess on a free port.

## Captured red output

```
saturn/tests/test_mcp_timeout_ex3.py:42: AssertionError: call against a tool
  that sleeps 30s must abort within 10s wall clock; took ~30.0s. The
  streamablehttp_client defaults (timeout=30, sse_read_timeout=300) are too
  lax for the Web-UI tool-call surface — either pass a tighter
  sse_read_timeout, or wrap mgr.call's invoke step in asyncio.wait_for with
  a deadline.
======================== 1 failed, 3 warnings in 40.62s ========================
```

Full transcript: `.brutus/Saturn-ex3/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| Wall clock from `mgr.call(...)` start to return | `< 10.0s` |
| Return type | `dict` with key `"error"` |
| Error message contents (case-insensitive) | one of: `"timeout"`, `"timed out"`, `"deadline"`, `"exceeded"`, `"cancel"` |

Test fixture: `mcp.server.FastMCP` subprocess; tool `echo(text)` sleeps 30s
before returning (`FAKE_MCP_HANG=30.0`).

## Fix sketch (non-binding)

Two viable approaches:

1. **Wrap the invoke step**:
   ```python
   async def call(self, server, tool, arguments):
       ...
       try:
           return await asyncio.wait_for(
               _with_session(entry["url"], entry.get("auth_token"), invoke),
               timeout=5.0,
           )
       except asyncio.TimeoutError:
           return {"error": f"MCP tool '{tool}' on '{server}' timed out after 5s"}
   ```

2. **Tighten transport timeouts** at `streamablehttp_client(..., sse_read_timeout=5)`.
   Less precise (covers connection-level idle, not tool-call wall clock).

Approach (1) is cleaner because the deadline is per-call, not per-stream.

## Out of scope

- Configurable per-tool deadlines (some tools legitimately need >5s). File
  as **Saturn-ex3.config** if needed; default-tight is correct for now.
- Server-side cancellation propagation (telling the MCP server to abort the
  in-flight tool). Out of MCP SDK's surface today.
- Retry on timeout. Don't retry by default — failing fast is the user-facing
  win.
- Concurrent in-flight tool calls (the current `MCPClientManager` does not
  multiplex; one call per invocation is the contract).

## Implementer

athena will route. Suggested: **hardener**. ETA: ~10 min.

## Transcript

`.brutus/Saturn-ex3/transcript.md`
