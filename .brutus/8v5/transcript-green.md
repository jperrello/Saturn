# 8v5 GREEN — saturn.runner.build_app() unifies inline + server.module auth

*2026-05-04T19:43:12Z by Showboat 0.6.1*
<!-- showboat-id: f03b12c4-2838-4ec7-b0a6-4503b4d57b55 -->

Implementation: new saturn.runner.build_app(config) is single dispatch. Inline branch keeps ServiceRunner.create_app() (Depends(auth)). server.module branch imports the module's FastAPI app and wraps it via _wrap_with_auth — a thin ASGI wrapper that intercepts /v1/* requests, validates bearer via hmac.compare_digest against SATURN_RUNNER_TOKEN, returns 401 + WWW-Authenticate: Bearer otherwise; non-/v1 + lifespan scopes pass through untouched. Wrapper is fresh per build_app call so module-level mod.app is never mutated (avoids middleware-stacking under repeated test imports). run_service collapsed to single-branch app = build_app(config); svc_runner pulled from app.state.runner when inline.

```bash
python3 -m pytest saturn/tests/test_server_module_auth.py -v 2>&1 | tail -15
```

```output
saturn/tests/test_server_module_auth.py::test_server_module_app_models_requires_auth[saturn.servers.claude] PASSED [ 58%]
saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.fallback] PASSED [ 66%]
saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.ollama] PASSED [ 75%]
saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.claude] PASSED [ 83%]
saturn/tests/test_server_module_auth.py::test_server_module_app_wrong_token_rejects PASSED [ 91%]
saturn/tests/test_server_module_auth.py::test_server_module_app_correct_token_passes PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 12 passed, 1 warning in 0.76s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_runner.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 52 passed, 2 warnings in 6.67s ========================
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
