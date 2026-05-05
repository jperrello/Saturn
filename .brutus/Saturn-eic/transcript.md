# Saturn-eic / cbt.2.c.large — MCP oversized-payload guard

*2026-05-05T05:25:49Z by Showboat 0.6.1*
<!-- showboat-id: f42ac36e-0380-4091-aec1-c5adf3ba9332 -->

Red. mcp_client.call buffers 10 MiB straight through (total_content_bytes=10485760). Test asserts >=1 of (a) error with size hint, (b) truncated flag, (c) silent cap <= 2 MiB. Currently none. Shared FastMCP fixture from conftest_mcp.py with blob_mb=10. NO MOCKS.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_mcp_large_eic.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
    @pytest.mark.fake_mcp(blob_mb=10)

saturn/tests/test_mcp_large_eic.py::test_oversized_mcp_payload_is_guarded
  /Users/jperr/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/lib/python3.12/contextlib.py:105: DeprecationWarning: Use `streamable_http_client` instead.
    self.gen = func(*args, **kwds)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 failed, 3 warnings in 6.21s =========================
```
