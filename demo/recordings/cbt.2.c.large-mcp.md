# cbt.2.c.large — hard-reject oversized MCP tool payloads

**Bead:** Saturn-eic   **Commit:** `4961da8`

A misbehaving MCP tool returning a 10 MiB blob was previously buffered
straight through, blowing the chat-context budget and risking OOM at
scale.

Fix: after `call_tool()` returns, sum the text-content bytes; if the
total exceeds `LARGE_RESULT_BYTES = 1 MiB` (`1024 * 1024`), discard
the payload and return:

```json
{"error": "MCP tool '<name>' returned <n> bytes (><LARGE_RESULT_BYTES> ceiling); refusing oversized payload"}
```

The model sees a normal tool error and the chat-context budget is
preserved.

## Reproducer (real fake-MCP fixture returning a 10 MiB text blob)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_mcp_large_eic.py
```

`@pytest.mark.fake_mcp(blob_mb=10)` spins a real MCP server whose tool
handler returns 10 MiB of text content. The test asserts the
`MCPClientManager.call()` return contains the size-overflow error
string and not the blob.

## Captured output

```text
saturn/tests/test_mcp_large_eic.py::test_oversized_mcp_payload_is_guarded PASSED
========================= 1 passed in <Ns> ============================
```

## Why this matters

Closes the third of three cbt.2.c MCP failure modes (unreachable /
timeout / oversized). The 1 MiB ceiling is a conservative cut — large
enough to fit any reasonable structured tool result, small enough that
even a hostile or buggy tool can't drag down a Saturn host. The error
shape matches the unreachable + timeout fixes, so a downstream chat UI
can render all three with the same glyph.
