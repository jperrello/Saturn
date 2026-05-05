# qj5.16.2 web admin server-side auth — red phase

*2026-05-04T19:23:59Z by Showboat 0.6.1*
<!-- showboat-id: c0312a64-8552-4cfd-9713-020050f93b71 -->

Spec: every /api/{services,admin,system,mcp}/* route on saturn/web.py must require admin_token_env (or admin session) server-side. sessionStorage-only gate is theatre — forged cookies/headers must NOT bypass. Public set: /api/admin/auth (issues token), /api/discover, /v1/health, static. Source: CONFIG_FIELDS.md A.5 auth matrix + SECURITY_AUDIT.md F-4.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_web_admin_auth.py -v 2>&1 | tail -60
```

```output
2026-05-04 12:24:17,297 - INFO - HTTP Request: GET http://testserver/api/admin/config "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/admin/config "HTTP/1.1 200 OK"
______________________ test_forged_header_does_not_bypass ______________________

client = <starlette.testclient.TestClient object at 0x10c29dd00>

    def test_forged_header_does_not_bypass(client):
        r = client.get("/api/admin/config", headers={"X-Admin": "true", "X-Saturn-Admin": "1"})
>       assert r.status_code == 401
E       assert 200 == 401
E        +  where 200 = <Response [200 OK]>.status_code

saturn/tests/test_web_admin_auth.py:72: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-05-04 12:24:17,317 - INFO - HTTP Request: GET http://testserver/api/admin/config "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/api/admin/config "HTTP/1.1 200 OK"
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

saturn/tests/test_web_admin_auth.py::test_forged_session_cookie_does_not_bypass
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[GET-/api/services-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/services-body1]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[DELETE-/api/services/nonexistent-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/services/nonexistent/start-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/services/nonexistent/stop-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[GET-/api/admin/config-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/admin/config-body6]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/system/tunnel/start-body7]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/system/tunnel/stop-body8]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[GET-/api/system/status-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[GET-/api/mcp/servers-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[POST-/api/mcp/servers-body11]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_without_auth[DELETE-/api/mcp/servers/nonexistent-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[GET-/api/services-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/services-body1]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[DELETE-/api/services/nonexistent-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/services/nonexistent/start-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/services/nonexistent/stop-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[GET-/api/admin/config-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/admin/config-body6]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/system/tunnel/start-body7]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/system/tunnel/stop-body8]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[GET-/api/system/status-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[GET-/api/mcp/servers-None]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[POST-/api/mcp/servers-body11]
FAILED saturn/tests/test_web_admin_auth.py::test_protected_route_401_with_wrong_bearer[DELETE-/api/mcp/servers/nonexistent-None]
FAILED saturn/tests/test_web_admin_auth.py::test_admin_config_auth_matrix - A...
FAILED saturn/tests/test_web_admin_auth.py::test_forged_session_cookie_does_not_bypass
FAILED saturn/tests/test_web_admin_auth.py::test_forged_header_does_not_bypass
================== 29 failed, 3 passed, 2 warnings in 22.54s ===================
```
