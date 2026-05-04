# qj5.16.10 GREEN — /api/usage* admin auth + DB path honors SATURN_DATA_DIR + drop XFF in _client_ip

*2026-05-04T19:34:27Z by Showboat 0.6.1*
<!-- showboat-id: d1dca53e-5a52-4607-a99e-37e22f0aa5e6 -->

Implementation: (1) Depends(require_admin) on GET /api/usage and GET /api/usage/history. (2) DB_PATH now honors SATURN_DATA_DIR env (was hardcoded; tests need isolation). (3) _client_ip no longer honors X-Forwarded-For (the cross-row admin-read test depends on POST and GET resolving the same caller; F-3 trusted_proxies allowlist is still its own bead, but blindly trusting untrusted XFF was unsafe regardless). UsageReport schema unchanged — Pydantic ignores extra body.user_id, so forged body field has no attribution effect (test 6 passes). POST /api/usage/report stays unauth + self-keyed.

```bash
python3 -m pytest saturn/tests/test_usage_auth.py -v 2>&1 | tail -10
```

```output
saturn/tests/test_usage_auth.py::test_usage_report_forged_user_id_does_not_attribute PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 6 passed, 1 warning in 0.86s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 39 passed, 2 warnings in 6.52s ========================
```
