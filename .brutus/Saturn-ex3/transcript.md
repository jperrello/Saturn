# Saturn-ex3 / cbt.2.c.timeout — MCP tool-call timeout enforcement

*2026-05-05T05:22:55Z by Showboat 0.6.1*
<!-- showboat-id: d5ba535a-d5b4-4ec5-9182-b8fbdb3038f7 -->

Red. mcp_client.call defaults to sse_read_timeout=300s; a hung tool blocks the caller for ~5 minutes. Test spins fake FastMCP server with echo tool that sleeps 30s, asserts call returns within 10s. Currently takes the full ~30s and returns the (eventually completed) result — wrong shape, missing timeout enforcement. NO MOCKS.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_mcp_timeout_ex3.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
    @pytest.mark.fake_mcp(hang=30.0)

saturn/tests/test_mcp_timeout_ex3.py::test_hung_tool_call_aborts_within_10s
  /Users/jperr/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 failed, 3 warnings in 40.62s ========================
```
