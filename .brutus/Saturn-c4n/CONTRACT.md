# CONTRACT — Saturn-c4n / cbt.2.c: MCP edge — unreachable server error clarity

**Status:** RED. 1 test pinned. Behavior is missing.
**Implementer:** athena will route (recommended: hardener — small-scope error wrap in `saturn/mcp_client.py`).

## Spec restatement (falsifiable)

`MCPClientManager.call(server, tool, args)` against a configured server whose
URL points at an unreachable host MUST return a `dict` whose `"error"` value:

1. Returns within 5s wall clock (already true today; test pins it as a
   regression invariant).
2. Does NOT leak the raw anyio text `"unhandled errors in a TaskGroup
   (1 sub-exception)"` — this is uninformative to a user.
3. Mentions one of: `unreachable`, `connection`, `refused`, `connect`,
   the host (`127.0.0.1`), or the configured server name.

The companion edges from RUN_BRIEF_MAY05.md §A.2 — tool-call timeout
enforcement and oversized-result handling — require a fake MCP server
implementing the protocol. Filed as **cbt.2.c.timeout** and **cbt.2.c.large**
sub-beads. Out of scope for this contract.

## Test files

- `saturn/tests/test_mcp_edges_cbt2c.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_mcp_edges_cbt2c.py --no-header -rN --tb=short
```

No external dependency. Closed-port TCP attempt against `127.0.0.1:1`.

## Captured red output

```
saturn/tests/test_mcp_edges_cbt2c.py:61: AssertionError: error message must
  not leak the raw anyio TaskGroup text; got 'unhandled errors in a TaskGroup
  (1 sub-exception)'. Wrap the underlying error so the user sees something
  actionable.
======================== 1 failed, 2 warnings in 0.97s =========================
```

Full transcript: `.brutus/Saturn-c4n/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| `time.time() - t0` (call latency) | `< 5.0` |
| `res` shape | `dict` with key `"error"` |
| `res["error"]` does NOT contain | `"taskgroup"` (case-insensitive) or `"sub-exception"` |
| `res["error"]` DOES contain at least one of | `"unreachable" / "connection" / "refused" / "connect" / "127.0.0.1" / "dead-mcp-server" / "host"` (case-insensitive) |

## Fix sketch (non-binding)

In `saturn/mcp_client.py:69 MCPClientManager.call`, the `except Exception as e`
catch can wrap with `ExceptionGroup` unwrapping plus a clear message:

```python
except* (ConnectionError, OSError) as eg:
    return {"error": f"MCP server '{server}' unreachable at {entry['url']}: {eg.exceptions[0]}"}
except Exception as e:
    return {"error": f"MCP server '{server}' failed: {e}"}
```

Implementer is free to use any approach that satisfies the oracle.

## Out of scope

- Tool-call timeout (slow-but-reachable server) — cbt.2.c.timeout.
- Oversized result truncation — cbt.2.c.large.
- Other MCP error classes (auth failure, protocol mismatch, etc.).
- The deprecation warning `"Use streamable_http_client instead"` from the MCP
  SDK — separate housekeeping bead if anyone cares.
- Any change to `streamablehttp_client` itself.

## Implementer

athena will route. Suggested: **hardener** — small wrap in `saturn/mcp_client.py:79`.

## Transcript

`.brutus/Saturn-c4n/transcript.md`
