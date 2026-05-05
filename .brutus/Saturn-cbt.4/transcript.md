# Saturn-cbt.4 — client-side failover (FULL contract)

*2026-05-05T04:46:43Z by Showboat 0.6.1*
<!-- showboat-id: 34bcec37-54c4-4905-82e4-697f7ae5ed33 -->

Red phase. Surface=/api/system/chat. Sticky=X-Saturn-Conversation-Id header. cbt.4.0=saturn_meta lift to /api/system/chat with new routing.events list. Two real FastAPI peer subprocesses, NO MOCKS. All 4 oracle bullets fail because behavior is missing.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_failover_cbt4.py --no-header -rN --tb=line 2>&1 | tail -15
```

```output
----------------------------- Captured stderr call -----------------------------
2026-05-04 21:46:52,467 - INFO - HTTP Request: POST http://127.0.0.1:60157/v1/chat/completions "HTTP/1.1 200 OK"
2026-05-04 21:46:52,469 - INFO - HTTP Request: POST http://testserver/api/system/chat "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: POST http://127.0.0.1:60157/v1/chat/completions "HTTP/1.1 200 OK"
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/api/system/chat "HTTP/1.1 200 OK"
/Users/jperr/Documents/Saturn/saturn/tests/test_failover_cbt4.py:351: AssertionError: requesting a model no peer advertises must fail loud (404 or 502), not silently route; got status=200, body=data: {}
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 4 failed, 1 warning in 8.54s =========================
```
