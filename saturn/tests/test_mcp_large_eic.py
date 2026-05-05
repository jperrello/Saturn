"""Saturn-eic / cbt.2.c.large — MCP tool oversized-result guard.

Brutus contract. Per RUN_BRIEF_MAY05.md §A.2 (cbt.2.c). When an MCP tool
returns a payload larger than a reasonable ceiling, `MCPClientManager.call()`
MUST refuse-or-truncate rather than buffer arbitrary memory and ship the
whole thing to the caller (and ultimately the chat context).

Today `saturn/mcp_client.py:74-77` does:

    return {"content": [c.model_dump() for c in result.content],
            "isError": result.isError}

— no size check. A 10 MiB blob from a misbehaving tool gets faithfully
buffered into the chat surface, blowing context budget and risking OOM.

Falsifiable oracle: against a fake MCP server whose `echo` tool returns
10 MiB of `"x"`, `MCPClientManager.call("fake-mcp", "echo", {"text":"hi"})`
MUST satisfy at least ONE of:

  (a) `res["error"]` is set with a message mentioning size / large /
      ceiling / bytes (oversized payload rejected loud), OR
  (b) `res` contains a truncation signal — any one of:
      `res["truncated"] is True`,
      `res["isError"] is True` paired with a size-mentioning content text,
      a content entry with key `truncated` set, OR
  (c) the cumulative size of all returned content text is <= 2 MiB
      (silently truncated to a sane ceiling).

The implementer's choice between (a) hard-fail, (b) flag, (c) silent cap is
NOT prescribed — but doing none of them (the current behavior) is forbidden.

NO MOCKS. Real `MCPClientManager`, real `mcp.server.FastMCP` subprocess.
"""

import asyncio
import time

import pytest

from .conftest_mcp import fake_mcp  # noqa: F401  (pytest fixture)


pytestmark = pytest.mark.timeout(60)


def _content_text_total(res) -> int:
    total = 0
    for c in (res.get("content") or []):
        if isinstance(c, dict):
            t = c.get("text")
            if isinstance(t, str):
                total += len(t.encode("utf-8"))
    return total


@pytest.mark.fake_mcp(blob_mb=10)
def test_oversized_mcp_payload_is_guarded(fake_mcp):
    from saturn.mcp_client import MCPClientManager
    mgr = MCPClientManager()

    t0 = time.time()
    res = asyncio.run(mgr.call("fake-mcp", "echo", {"text": "hi"}))
    elapsed = time.time() - t0

    assert isinstance(res, dict), f"call must return a dict; got {type(res).__name__}"
    assert elapsed < 30.0, (
        f"call must not take longer than 30s on a 10 MiB payload; took {elapsed:.2f}s. "
        f"If a guard is in place this should be fast; if not, transport buffering may "
        f"still complete eventually but timing is a secondary signal."
    )

    SIZE_HINTS = ("size", "large", "oversize", "ceiling", "bytes", "byte cap",
                  "too big", "too large", "truncat")
    err = str(res.get("error") or "").lower()
    err_is_size = bool(res.get("error")) and any(h in err for h in SIZE_HINTS)

    truncated_flag = (
        res.get("truncated") is True
        or (res.get("isError") is True and any(h in str(c).lower() for h in SIZE_HINTS for c in (res.get("content") or [])))
        or any(isinstance(c, dict) and c.get("truncated") is True for c in (res.get("content") or []))
    )

    total_bytes = _content_text_total(res)
    silent_cap_ok = total_bytes <= 2 * 1024 * 1024  # 2 MiB

    guarded = err_is_size or truncated_flag or silent_cap_ok
    assert guarded, (
        f"MCPClientManager.call returned an unguarded oversized payload. "
        f"Test sent a tool that returns 10 MiB; the result was buffered straight "
        f"through. Implementer must pick one of: "
        f"(a) raise via res['error'] with a size hint, "
        f"(b) set res['truncated']=True (or equivalent flag), or "
        f"(c) silently cap total content text <= 2 MiB. "
        f"Observed: total_content_bytes={total_bytes}, "
        f"keys={sorted(res.keys())!r}, "
        f"error={res.get('error')!r}, "
        f"isError={res.get('isError')!r}, "
        f"truncated={res.get('truncated')!r}."
    )
