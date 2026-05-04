# qj5.14 GREEN — boot validators (security half) + LLM-honoured config (Ollama half)

*2026-05-04T22:07:18Z by Showboat 0.6.1*
<!-- showboat-id: 099a6726-a68b-47da-b959-11a79eb35697 -->

Two halves landed in single PR. Security: 8 boot validators C.1.1-C.1.8 in new saturn/boot_validators.py (lightweight, no heavy deps so it loads fast enough to exit within the 2s _boot deadline). _check_admin_password_env / _check_admin_token_env / _check_runner_token_env / _check_lan_exposure_requires_auth / _check_beacon_budgets / _check_tls_pair / _check_trusted_proxies_cidrs / _check_cors_no_wildcard. saturn/__main__.py 'web' command runs validators BEFORE 'from .web import main' import (which is ~2-5s) so structured errors aggregate to stderr and sys.exit(1) before uvicorn can start. SATURN_DEV_MODE=1 short-circuits the exit, errors still log. SATURN_ADMIN_CONFIG_PATH respected for trusted_proxies + cors_origins reads. SATURN_SERVICES_DIR respected for beacon-TOML scan. Backstop validators retained inside saturn.web.main() too. LLM-honoured: ChatRequest gained 'stream: Optional[bool]'; /api/chat now branches on stream==False to make a non-streaming upstream POST and return JSON directly (existing streaming path unchanged). ServiceCreate accepts nested {upstream:{base_url,api_key_env}} OR flat fields (test fixture uses nested shape). saturn/config.py SERVICES_DIR respects SATURN_SERVICES_DIR env. Bonus: tests/harness/web.py serve() now seeds SATURN_RUNNER_TOKEN + SATURN_ADMIN_PASSWORD + SATURN_BIND_HOST=127.0.0.1 defaults so existing harness selftest stays green under the new boot-time refusal.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_boot_validators.py --timeout=30 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 27 passed, 1 warning in 33.45s ========================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_config_honoured.py --timeout=120 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================== 4 passed, 1 skipped, 1 warning in 17.05s ===================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_runner.py saturn/tests/test_identity.py saturn/tests/test_known_nodes.py saturn/tests/test_resolve_trust_rebind.py saturn/tests/test_admin_config_qj5_13.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================= 119 passed, 2 warnings in 118.81s (0:01:58) ==================
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
