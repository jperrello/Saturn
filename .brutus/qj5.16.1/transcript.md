# qj5.16.1 runner auth + safe bind — red phase

*2026-05-04T19:19:53Z by Showboat 0.6.1*
<!-- showboat-id: e525e89a-f8c1-4262-9733-4700b7b1a89f -->

Spec: /v1/health, /v1/models, /v1/chat/completions on the runner must require a bearer token (SATURN_RUNNER_TOKEN env). Default bind host for run_service() and saturn-runner CLI must be 127.0.0.1; binding to 0.0.0.0 is explicit opt-in.

```bash
cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_runner_auth.py -v 2>&1 | tail -40
```

```output
/Users/jperr/.cache/uv/archive-v0/sOzsRhPmu6jhLisaHpc9s/bin/python3: No module named pytest
```

```bash
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_runner_auth.py -v 2>&1 | tail -50
```

```output
WARNING  saturn.runner:runner.py:339 No models fetched at startup
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/v1/health "HTTP/1.1 200 OK"
INFO     httpx:_client.py:1025 HTTP Request: GET http://testserver/v1/health "HTTP/1.1 200 OK"
INFO     saturn.runner:runner.py:345 Shutting down auth-runner service...
__________________ test_run_service_default_bind_is_loopback ___________________

    def test_run_service_default_bind_is_loopback():
        sig = inspect.signature(run_service)
>       assert sig.parameters["host"].default == "127.0.0.1", (
            f"run_service default host must be 127.0.0.1 (loopback), "
            f"got {sig.parameters['host'].default!r}"
        )
E       AssertionError: run_service default host must be 127.0.0.1 (loopback), got '0.0.0.0'
E       assert '0.0.0.0' == '127.0.0.1'
E         
E         - 127.0.0.1
E         + 0.0.0.0

saturn/tests/test_runner_auth.py:72: AssertionError
_________________ test_main_argparse_default_host_is_loopback __________________

    def test_main_argparse_default_host_is_loopback():
        import argparse
        import saturn.runner as runner_mod
    
        src = inspect.getsource(runner_mod.main)
>       assert '"--host"' in src and 'default="127.0.0.1"' in src, (
            "main() argparse must default --host to 127.0.0.1; "
            "0.0.0.0 must be explicit opt-in"
        )
E       AssertionError: main() argparse must default --host to 127.0.0.1; 0.0.0.0 must be explicit opt-in
E       assert ('"--host"' in 'def main() -> int:\n    parser = argparse.ArgumentParser(description="Run a Saturn service from config")\n    parser.add_argument("name", nargs="?", help="Service name (from ~/.saturn/services/)")\n    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")\n    parser.add_argument("--port", type=int, default=None, help="Port to bind to")\n    parser.add_argument("--list", "-l", action="store_true", help="List available services")\n    args = parser.parse_args()\n\n    if args.list:\n        configs = list_service_configs()\n        if not configs:\n            print("No services configured.")\n            print(f"Create one with: saturn config new")\n            return 0\n\n        print("Available services:")\n        for name, cfg, is_builtin in configs:\n            source = " (built-in)" if is_builtin else ""\n            beacon = " [beacon]" if cfg.beacon.enabled else ""\n            print(f"  {name}: {cfg.api_type} @ {cfg.upstream.base_url}{beacon}{source}")\n        return 0\n\n    if not args.name:\n        parser.print_help()\n        return 1\n\n    config = load_service_config(args.name)\n    if not config:\n        print(f"Service \'{args.name}\' not found in {SERVICES_DIR}", file=sys.stderr)\n        print(f"Create it with: saturn config new")\n        return 1\n\n    return run_service(config, host=args.host, port=args.port)\n' and 'default="127.0.0.1"' in 'def main() -> int:\n    parser = argparse.ArgumentParser(description="Run a Saturn service from config")\n    parser.add_argument("name", nargs="?", help="Service name (from ~/.saturn/services/)")\n    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")\n    parser.add_argument("--port", type=int, default=None, help="Port to bind to")\n    parser.add_argument("--list", "-l", action="store_true", help="List available services")\n    args = parser.parse_args()\n\n    if args.list:\n        configs = list_service_configs()\n        if not configs:\n            print("No services configured.")\n            print(f"Create one with: saturn config new")\n            return 0\n\n        print("Available services:")\n        for name, cfg, is_builtin in configs:\n            source = " (built-in)" if is_builtin else ""\n            beacon = " [beacon]" if cfg.beacon.enabled else ""\n            print(f"  {name}: {cfg.api_type} @ {cfg.upstream.base_url}{beacon}{source}")\n        return 0\n\n    if not args.name:\n        parser.print_help()\n        return 1\n\n    config = load_service_config(args.name)\n    if not config:\n        print(f"Service \'{args.name}\' not found in {SERVICES_DIR}", file=sys.stderr)\n        print(f"Create it with: saturn config new")\n        return 1\n\n    return run_service(config, host=args.host, port=args.port)\n')

saturn/tests/test_runner_auth.py:83: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_runner_auth.py::test_health_401_without_auth - Asser...
FAILED saturn/tests/test_runner_auth.py::test_models_401_without_auth - Asser...
FAILED saturn/tests/test_runner_auth.py::test_chat_completions_401_without_auth
FAILED saturn/tests/test_runner_auth.py::test_health_401_with_wrong_token - a...
FAILED saturn/tests/test_runner_auth.py::test_correct_token_succeeds_and_wrong_token_rejects
FAILED saturn/tests/test_runner_auth.py::test_run_service_default_bind_is_loopback
FAILED saturn/tests/test_runner_auth.py::test_main_argparse_default_host_is_loopback
========================= 7 failed, 1 warning in 0.39s =========================
```
