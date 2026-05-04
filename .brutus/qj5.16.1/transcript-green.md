# qj5.16.1 GREEN — runner /v1/* auth + loopback default

*2026-05-04T19:23:23Z by Showboat 0.6.1*
<!-- showboat-id: 8246883a-6274-46de-a1f7-d996033a8bcd -->

Implementation: hmac.compare_digest bearer-token check on /v1/* via FastAPI Depends. Token env name: runner_token_env (default SATURN_RUNNER_TOKEN). 401 carries WWW-Authenticate: Bearer. run_service host default and main() --host default flipped to 127.0.0.1.

```bash
python3 -m pytest saturn/tests/test_runner_auth.py -v 2>&1 | tail -15
```

```output
saturn/tests/test_runner_auth.py::test_models_401_without_auth PASSED    [ 28%]
saturn/tests/test_runner_auth.py::test_chat_completions_401_without_auth PASSED [ 42%]
saturn/tests/test_runner_auth.py::test_health_401_with_wrong_token PASSED [ 57%]
saturn/tests/test_runner_auth.py::test_correct_token_succeeds_and_wrong_token_rejects PASSED [ 71%]
saturn/tests/test_runner_auth.py::test_run_service_default_bind_is_loopback PASSED [ 85%]
saturn/tests/test_runner_auth.py::test_main_argparse_default_host_is_loopback PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 7 passed, 1 warning in 0.45s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner.py -v 2>&1 | tail -12
```

```output
saturn/tests/test_runner.py::test_service_runner_health PASSED           [ 71%]
saturn/tests/test_runner.py::test_service_runner_models_empty PASSED     [ 85%]
saturn/tests/test_runner.py::test_write_creates_run_dir PASSED           [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 7 passed, 1 warning in 0.38s =========================
```
