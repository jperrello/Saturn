# Saturn-cbt.2.a — long-message HTTP-level regression guard

*2026-05-05T04:50:14Z by Showboat 0.6.1*
<!-- showboat-id: a0bf7a3e-aafe-48f7-8c74-3cff67da0a73 -->

Regression-guard contract (no red phase). The HTTP-layer behavior 'long user messages stream promptly with intact saturn_meta receipt' already works on /api/chat per qj5.15. Test pins the invariant so a future regression in the streaming proxy or receipt emitter is caught. The TRUE UI-freeze concern (browser repaint cadence, scroll buffer, virtualization) needs Bombadil/Playwright and is deferred to cbt.2.a.ui — out of brutus's lane (TS/Playwright); should route to a UI crew member.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_long_messages_cbt2a.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
saturn/tests/test_long_messages_cbt2a.py .                               [100%]

=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 passed, 1 warning in 3.47s =========================
```
