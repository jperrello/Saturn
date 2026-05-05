"""Saturn-ex3 / cbt.2.c.timeout — MCP tool-call timeout enforcement.

Brutus contract. Per RUN_BRIEF_MAY05.md §A.2 (cbt.2.c). When an MCP server
accepts a connection but stalls on a tool call (e.g., the tool's own logic
hangs / runs longer than the user can wait), `MCPClientManager.call()` MUST
abort within a bounded wall-clock time and return a structured error.

The current code (`saturn/mcp_client.py:69-80`) defers to
`streamablehttp_client`'s defaults: `timeout=30, sse_read_timeout=300`. A
hung tool call on a healthy connection therefore blocks the caller for up
to ~5 minutes, which is unacceptable for the Web-UI MCP-tools surface.

Falsifiable oracle: against a fake MCP server whose `echo` tool sleeps 30s,
`MCPClientManager.call("fake-mcp", "echo", {"text":"hi"})` MUST return
within 10s with a `dict` whose `error` field mentions timeout / deadline /
exceeded.

NO MOCKS. Real `MCPClientManager`, real `mcp.server.FastMCP` subprocess.
"""

import asyncio
import time

import pytest

from .conftest_mcp import fake_mcp  # noqa: F401  (pytest fixture)


pytestmark = pytest.mark.timeout(60)


@pytest.mark.fake_mcp(hang=30.0)
def test_hung_tool_call_aborts_within_10s(fake_mcp):
    from saturn.mcp_client import MCPClientManager
    mgr = MCPClientManager()

    t0 = time.time()
    res = asyncio.run(mgr.call("fake-mcp", "echo", {"text": "hi"}))
    elapsed = time.time() - t0

    assert elapsed < 10.0, (
        f"call against a tool that sleeps 30s must abort within 10s wall clock; "
        f"took {elapsed:.2f}s. The streamablehttp_client defaults (timeout=30, "
        f"sse_read_timeout=300) are too lax for the Web-UI tool-call surface — "
        f"either pass a tighter sse_read_timeout, or wrap mgr.call's invoke step "
        f"in asyncio.wait_for with a deadline."
    )
    assert isinstance(res, dict) and "error" in res, (
        f"timed-out call must return {{'error': <str>}}; got {res!r}"
    )
    msg = str(res["error"]).lower()
    hints = ("timeout", "timed out", "deadline", "exceeded", "cancel")
    assert any(h in msg for h in hints), (
        f"timeout error message must mention timeout/deadline/exceeded so the user "
        f"knows what happened; got {res['error']!r}. Expected one of {hints!r}."
    )
