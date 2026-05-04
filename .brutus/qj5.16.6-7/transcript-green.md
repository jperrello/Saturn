# qj5.16.6+.7 GREEN — proxy body/query keys removed + leak surfaces sanitised

*2026-05-04T19:49:41Z by Showboat 0.6.1*
<!-- showboat-id: 5c71c2a5-5762-43e2-8e5a-7a36835d71f9 -->

Implementation: (F-5) ManualChatRequest gets model_config = ConfigDict(extra='forbid') and api_key field deleted → body-supplied api_key now 422; proxy_chat reads inbound Authorization: Bearer header verbatim and forwards; upstream non-200 SSE chunk replaced with constant {"error":"upstream <code>"}. (F-6) proxy_models drops api_key Query param, manually rejects ?api_key=… with 422; reads inbound Authorization header; 502 surface dropped exception interpolation — logs upstream error server-side via logger.warning, returns constant 'Failed to fetch models' string. No UI change required (Web-UI already sends no api_key). Auth-gating these routes is intentionally out-of-scope per CONFIG_FIELDS A.5 / contract.

```bash
python3 -m pytest saturn/tests/test_proxy_no_body_keys.py -v 2>&1 | tail -10
```

```output
saturn/tests/test_proxy_no_body_keys.py::test_proxy_models_502_does_not_leak_upstream_details PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 6 passed, 1 warning in 4.01s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 57 passed, 2 warnings in 6.69s ========================
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
