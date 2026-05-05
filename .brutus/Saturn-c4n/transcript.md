# Saturn-c4n / cbt.2.c — MCP unreachable error clarity

*2026-05-05T04:55:53Z by Showboat 0.6.1*
<!-- showboat-id: 399e8a33-1b1e-486f-acc3-f0950fd13589 -->

Red phase. mcp_client.call against an unreachable URL leaks 'unhandled errors in a TaskGroup (1 sub-exception)' to the user. Test pins the requirement that the error string mentions reachability/host/connection. Real MCP client + real closed-port TCP attempt. Companion edges (tool-call timeout, oversized result) deferred to cbt.2.c.timeout / cbt.2.c.large — fake MCP server work.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_mcp_edges_cbt2c.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

saturn/tests/test_mcp_edges_cbt2c.py::test_unreachable_mcp_call_returns_human_error
  /Users/jperr/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 failed, 2 warnings in 0.97s =========================
```
