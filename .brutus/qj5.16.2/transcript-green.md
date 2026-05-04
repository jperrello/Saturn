# qj5.16.2 GREEN — saturn/web.py admin endpoint server-side auth

*2026-05-04T19:27:49Z by Showboat 0.6.1*
<!-- showboat-id: 807830fc-7432-40e3-a1ef-151558152039 -->

Implementation: require_admin Depends on every protected /api/{services,admin,system,mcp}/* route. Bearer-token check via hmac.compare_digest against env var named by SATURN_ADMIN_TOKEN_ENV (default SATURN_ADMIN_TOKEN). 401 carries WWW-Authenticate: Bearer. Public routes preserved: POST /api/admin/auth, GET /api/discover, GET /v1/health, static /{path}. Out-of-scope routes (/api/chat, /api/proxy/*, /api/models) intentionally untouched per CONTRACT (those take runner-token, not admin-token).

```bash
python3 -m pytest saturn/tests/test_web_admin_auth.py -v 2>&1 | tail -8
```

```output
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

saturn/tests/test_web_admin_auth.py::test_forged_session_cookie_does_not_bypass
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 32 passed, 2 warnings in 2.87s ========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py -v 2>&1 | tail -5
```

```output
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 7 passed, 1 warning in 0.57s =========================
```
