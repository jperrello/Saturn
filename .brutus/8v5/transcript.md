# Saturn-8v5 server.module auth bypass — red phase

*2026-05-04T19:40:03Z by Showboat 0.6.1*
<!-- showboat-id: 9209d644-8b83-43b5-9bed-7b9912b59a8e -->

Spec: saturn.runner must expose build_app(config: ServiceConfig) -> FastAPI as the single dispatch point used by run_service. For both branches (config.server.module set, or inline ServiceRunner), the returned app must require bearer auth on /v1/health, /v1/models, /v1/chat/completions per qj5.16.1. saturn/servers/{ollama,claude,fallback}.py app instances are imported verbatim today (saturn/runner.py:481), bypassing the wrapper added in qj5.16.1. F-1 effectively re-opened for the default deploy path.

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_server_module_auth.py -v 2>&1 | tail -25
```

```output
>       from saturn.runner import build_app
E       ImportError: cannot import name 'build_app' from 'saturn.runner' (/Users/jperr/Documents/Saturn/saturn/runner.py)

saturn/tests/test_server_module_auth.py:52: ImportError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_server_module_auth.py::test_inline_runner_still_requires_auth
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_health_requires_auth[saturn.servers.fallback]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_health_requires_auth[saturn.servers.ollama]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_health_requires_auth[saturn.servers.claude]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_models_requires_auth[saturn.servers.fallback]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_models_requires_auth[saturn.servers.ollama]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_models_requires_auth[saturn.servers.claude]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.fallback]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.ollama]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_chat_completions_requires_auth[saturn.servers.claude]
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_wrong_token_rejects
FAILED saturn/tests/test_server_module_auth.py::test_server_module_app_correct_token_passes
======================== 12 failed, 1 warning in 0.36s =========================
```
