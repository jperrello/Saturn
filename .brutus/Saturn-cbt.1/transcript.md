# Saturn-cbt.1 / qj5.15.2 — saturn_meta receipt lift

*2026-05-05T04:34:49Z by Showboat 0.6.1*
<!-- showboat-id: 60acd3e3-4ed2-4b38-89be-01fe24a9a337 -->

Red phase. Per PRE_SPECS_B3.md §17.F: lift saturn_meta envelope from /api/chat to (1) /api/proxy/chat, (2) ServiceRunner /v1/chat/completions streaming, (3) ServiceRunner /v1/chat/completions non-streaming. Real Ollama, no mocks. Tests fail because saturn_meta is absent from each surface — the right red shape.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_receipt_meta_lift.py --no-header -rN --tb=line 2>&1 | tail -25
```

```output
INFO     saturn.runner:runner.py:440 Cached 1 models
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/chat/completions "HTTP/1.1 200 OK"
INFO     saturn.runner:runner.py:448 Shutting down cbt1-runner-00cc9e service...
/Users/jperr/Documents/Saturn/saturn/tests/test_receipt_meta_lift.py:93: AssertionError: no chunk in the SSE stream carried `saturn_meta`. Per §17.F.2 the final chunk before `data: [DONE]` must include saturn_meta. Stream tail:
E   AssertionError: non-streaming /v1/chat/completions response MUST carry top-level saturn_meta key per §17.F.2.3; got keys=['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']
    assert 'saturn_meta' in {'choices': [{'finish_reason': 'stop', 'index': 0, 'message': {'content': '你好！有什么可以帮助你的吗？', 'role': 'assistant'}}], 'created': 1777955737, 'id': 'chatcmpl-906', 'model': 'qwen2.5:0.5b', ...}
----------------------------- Captured stderr call -----------------------------
2026-05-04 21:35:37,357 - INFO - Starting cbt1-runner-e61f78 service...
2026-05-04 21:35:37,359 - INFO - Cached 1 models
2026-05-04 21:35:37,581 - INFO - HTTP Request: POST http://testserver/v1/chat/completions "HTTP/1.1 200 OK"
2026-05-04 21:35:37,582 - INFO - Shutting down cbt1-runner-e61f78 service...
------------------------------ Captured log call -------------------------------
INFO     saturn.runner:runner.py:437 Starting cbt1-runner-e61f78 service...
INFO     saturn.runner:runner.py:440 Cached 1 models
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/v1/chat/completions "HTTP/1.1 200 OK"
INFO     saturn.runner:runner.py:448 Shutting down cbt1-runner-e61f78 service...
/Users/jperr/Documents/Saturn/saturn/tests/test_receipt_meta_lift.py:217: AssertionError: non-streaming /v1/chat/completions response MUST carry top-level saturn_meta key per §17.F.2.3; got keys=['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 failed, 1 warning in 5.53s =========================
```

Green phase. Hardener landed implementation in commit 347bdc9. Re-running the same 3 tests now must pass.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_receipt_meta_lift.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
saturn/tests/test_receipt_meta_lift.py ...                               [100%]

=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 passed, 1 warning in 4.31s =========================
```

(cbt.4 verification — moved here so the cbt.4 transcript can be standalone)
