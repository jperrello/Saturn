# CONTRACT — Saturn-eic / cbt.2.c.large: MCP oversized-payload guard

**Status:** RED. 1 test pinned.
**Implementer:** athena will route (recommended: hardener — small size check in `MCPClientManager.call` after `result.content` is in hand).

## Spec restatement (falsifiable)

When an MCP tool returns a payload larger than a sane ceiling, the current
`saturn/mcp_client.py:74-77` faithfully buffers and ships it through:

    return {"content": [c.model_dump() for c in result.content],
            "isError": result.isError}

A 10 MiB blob from a misbehaving tool gets routed straight to the chat
context, blowing prompt budget and risking OOM at scale. The fix MUST guard
the size, picking exactly **one** of three strategies:

  (a) **Hard reject** — `res["error"]` is set with a message mentioning
      `size`, `large`, `oversize`, `ceiling`, `bytes`, `byte cap`,
      `too big`, `too large`, or `truncat`.

  (b) **Flag truncation** — at least one of:
      `res["truncated"] is True`, OR
      `res["isError"] is True` paired with a size-mentioning content text, OR
      a content entry with `truncated=True`.

  (c) **Silent cap** — total content text bytes ≤ 2 MiB.

Implementer chooses; brutus does not prescribe. Doing **none** of the three
(today's behavior) is forbidden.

## Test files

- `saturn/tests/test_mcp_large_eic.py` (added; 1 test).
- `saturn/tests/conftest_mcp.py` (shared with Saturn-ex3; supports
  `@pytest.mark.fake_mcp(blob_mb=10)`).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_mcp_large_eic.py --no-header -rN --tb=short
```

No external dependency. `mcp.server.FastMCP` already in deps.

## Captured red output

```
saturn/tests/test_mcp_large_eic.py:96: AssertionError:
  MCPClientManager.call returned an unguarded oversized payload. Test sent a
  tool that returns 10 MiB; the result was buffered straight through. ...
  Observed: total_content_bytes=10485760, keys=['content', 'isError'],
  error=None, isError=False, truncated=None.
======================== 1 failed, 3 warnings in 6.21s =========================
```

10 MiB = 10 485 760 bytes — the entire payload made it through unchecked.
Full transcript: `.brutus/Saturn-eic/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| Wall clock | `< 30.0s` (sanity bound; not the primary signal) |
| Return type | `dict` |
| Guarded (any of (a), (b), (c)) | true |

The OR-shape gives the implementer freedom; the assertion message lays
out all three accepted paths verbatim so the choice is explicit, not
guessed.

## Fix sketch (non-binding)

```python
# in saturn/mcp_client.py:69-80
LARGE_RESULT_BYTES = 1024 * 1024          # 1 MiB ceiling

async def call(self, server, tool, arguments):
    ...
    raw_content = [c.model_dump() for c in result.content]
    total = sum(len(str(c.get("text",""))) for c in raw_content if isinstance(c, dict))
    if total > LARGE_RESULT_BYTES:
        return {"error": f"MCP tool '{tool}' on '{server}' returned {total} "
                         f"bytes (>{LARGE_RESULT_BYTES} ceiling); refusing"}
    return {"content": raw_content, "isError": result.isError}
```

Strategy (a). Implementer free to pick (b) or (c) instead.

## Out of scope

- Streaming-truncation (cap mid-stream rather than after full buffer). The
  MCP SDK doesn't surface partial content cleanly; revisit only if memory
  becomes a real concern.
- Per-tool ceiling overrides. File as **Saturn-eic.config** if needed.
- Surface in Web-UI when a result was truncated. UI lane.
- Token-aware truncation (truncating to fit context window rather than a
  byte ceiling). Token math is upstream of the MCP client; out of scope.

## Implementer

athena will route. Suggested: **hardener**. ETA: ~10 min.

## Transcript

`.brutus/Saturn-eic/transcript.md`
