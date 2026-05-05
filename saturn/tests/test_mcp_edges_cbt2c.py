"""Saturn-cbt.2.c — MCP edge cases at the client layer (Saturn-c4n).

Brutus contract per RUN_BRIEF_MAY05.md §A.2. The MCP client at
saturn/mcp_client.py wraps `mcp.client.streamable_http.streamablehttp_client`
without bounding error semantics. This contract pins one falsifiable bullet:

  **Unreachable-server error clarity.** When `MCPClientManager.call(server,
  tool, args)` is invoked and the configured server URL points at a closed
  TCP port (or otherwise unreachable host), the returned dict's `error` field
  MUST be a human-readable string that names the server and gives the user a
  hint about what failed (e.g. mentions "unreachable", "connection",
  "refused", or the URL/host). The current behavior leaks the raw
  `"unhandled errors in a TaskGroup (1 sub-exception)"` text from anyio,
  which is useless to a user trying to diagnose their MCP setup.

The companion bullets — tool-call timeout enforcement and oversized-result
handling — require a fake MCP server that speaks the protocol. They are
filed as cbt.2.c.timeout and cbt.2.c.large sub-beads (out of scope here).

NO MOCKS. Real `MCPClientManager`, real `streamablehttp_client`, real TCP
attempt against a closed port.
"""

import asyncio
import json
import re
import tempfile
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.timeout(30)


@pytest.fixture
def manager_with_dead_server(monkeypatch):
    import saturn.mcp_client as m
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    tmp.write(json.dumps([{"name": "dead-mcp-server", "url": "http://127.0.0.1:1/mcp"}]))
    tmp.flush()
    monkeypatch.setattr(m, "CONFIG_PATH", Path(tmp.name))
    return m.MCPClientManager()


def test_unreachable_mcp_call_returns_human_error(manager_with_dead_server):
    t0 = time.time()
    res = asyncio.run(manager_with_dead_server.call("dead-mcp-server", "anything", {}))
    elapsed = time.time() - t0

    assert elapsed < 5.0, (
        f"call against unreachable MCP server must fail fast (<5s); took {elapsed:.2f}s"
    )
    assert isinstance(res, dict) and "error" in res, (
        f"call must return {{'error': <str>}} on unreachable server; got {res!r}"
    )

    err = str(res["error"]).lower()
    # Reject the bare anyio TaskGroup leak — that string is useless to a user.
    assert "taskgroup" not in err and "sub-exception" not in err, (
        f"error message must not leak the raw anyio TaskGroup text; got {res['error']!r}. "
        f"Wrap the underlying error so the user sees something actionable."
    )
    # Must mention something about reachability or the configured target.
    hints = ("unreachable", "connection", "refused", "connect", "127.0.0.1", "dead-mcp-server", "host")
    assert any(h in err for h in hints), (
        f"error must hint at the unreachability / target server; expected one of {hints!r} "
        f"in the error text; got {res['error']!r}"
    )
