# Saturn-ggn / cbt.cross-client — /v1/* HTTP-stack parity

*2026-05-05T07:04:30Z by Showboat 0.6.1*
<!-- showboat-id: 683e4e28-dfcb-4496-ac5f-4e04ba3a49fd -->

GREEN on first run. urllib + httpx + subprocess curl all receive identical canonical forms across /v1/health, /v1/models, /v1/chat/completions stream + non-stream. Regression guard pinning the parity invariant. Go deferred (no harness) → Saturn-ggn.go.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_cross_client_ggn.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 passed, 1 warning in 2.36s =========================
```
