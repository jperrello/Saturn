# Saturn-8v5 green phase

*2026-05-04T19:44:44Z by Showboat 0.6.1*
<!-- showboat-id: 2b799992-7a93-4d70-9fe8-c992c2bab1c6 -->

Implementer 4227474. 57/57 across 8v5 + 16.1/16.2/16.10 auth suites.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_server_module_auth.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py 2>&1 | tail -5
```

```output
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/starlette/testclient.py:445: DeprecationWarning: Setting per-request cookies=<...> is being deprecated, because the expected behaviour on cookie persistence is ambiguous. Set cookies directly on the client instance instead.
    return super().request(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 57 passed, 2 warnings in 6.82s ========================
```
