# qj5.16.10 /api/usage* admin auth — red phase

*2026-05-04T19:30:54Z by Showboat 0.6.1*
<!-- showboat-id: de75bff6-42ef-41a3-bad6-41860ebd7388 -->

Spec: GET /api/usage and GET /api/usage/history must require admin_token_env (CONFIG_FIELDS A.5 + SECURITY_AUDIT §9). Caller-supplied user_id is admin-intentional read-any. POST /api/usage/report stays self-report keyed by _client_ip only. F-3 sub: today the user_id Query() lets any LAN peer iterate IPs and read everyone's daily token totals + N-day history.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_usage_auth.py -v 2>&1 | tail -25
```

```output
E       assert 200 == 401
E        +  where 200 = <Response [200 OK]>.status_code

saturn/tests/test_usage_auth.py:78: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-05-04 12:30:55,893 - INFO - HTTP Request: POST http://testserver/api/usage/report "HTTP/1.1 200 OK"
2026-05-04 12:30:55,895 - INFO - HTTP Request: GET http://testserver/api/usage?user_id=10.0.0.99 "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 HTTP Request: POST http://testserver/api/usage/report "HTTP/1.1 200 OK"
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/usage?user_id=10.0.0.99 "HTTP/1.1 200 OK"
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_usage_auth.py::test_usage_401_without_auth - Asserti...
FAILED saturn/tests/test_usage_auth.py::test_usage_history_401_without_auth
FAILED saturn/tests/test_usage_auth.py::test_usage_401_with_wrong_bearer - as...
FAILED saturn/tests/test_usage_auth.py::test_usage_admin_can_read_any_row - a...
FAILED saturn/tests/test_usage_auth.py::test_usage_history_auth_matrix - asse...
FAILED saturn/tests/test_usage_auth.py::test_usage_report_forged_user_id_does_not_attribute
========================= 6 failed, 1 warning in 0.89s =========================
```
