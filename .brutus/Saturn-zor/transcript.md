# Saturn-zor / cbt.4.sec.token — /api/system/chat auth gate

*2026-05-05T06:59:55Z by Showboat 0.6.1*
<!-- showboat-id: 9a07ac86-8c4a-4c95-80f7-9ad8e28ce4e3 -->

Red. /api/system/chat at saturn/web.py:1062-1063 has no Depends(require_admin); both no-auth and wrong-token return 502 (passes through to business logic). Other /api/system/* endpoints (status, tunnel/*) properly gate. Real saturn web subprocess.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_system_chat_auth_zor.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
==================== 2 failed, 1 passed, 1 warning in 8.05s ====================
```
