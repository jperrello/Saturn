# Saturn-6sb GREEN — per-service editor on Configure page (qj5.13 commit 3)

*2026-05-05T01:05:24Z by Showboat 0.6.1*
<!-- showboat-id: c73148a5-0380-49a6-a483-c1a6b96d4d5a -->

5/5 contract tests + 4/4 hft regression + 9 prior auth/runner/identity/admin_config suites green; harness ALL OK. Implementation: (a) New per-service-editor fieldset added inside admin-configure-page in Web-UI/index.html — list (#per-service-list class checklist), Add button (+ Add Service), and create/edit form with #cfg-name + #cfg-base-url + #cfg-api-key-env + #cfg-deployment + #cfg-api-type + #cfg-priority + #cfg-max-budget-usd + #cfg-require-runner-token. (b) JS in app.js: loadPerServiceList fetches /api/services on mount + every 1s when no form input is focused, renders rows with data-service attr + Edit + Delete buttons. saveService POSTs /api/services for create, PUTs /api/services/<name> for edit. deleteService confirms via window.confirm and DELETEs. (c) NEW /admin/configure handler change: serves FULL index.html (not slim shell) with admin-configure-page hidden→visible class swap + ac-* value pre-fill + injected <base href='/'> so relative asset URLs (app.js, styles.css) resolve correctly under /admin/* paths. Auth: /admin/configure route NOT gated (HTML render only); the fetch override in tests + UI both add bearer to /api/* calls — auth enforced at API endpoints. (d) NEW PUT /api/services/{name} endpoint for UI Edit. (e) Renamed legacy 'API Key' label/id to 'API Key — env var name' / cfg-api-key-env-legacy (preserves invariant: configs hold env-var NAMES never values). Renamed connector display 'API Key' label to 'Bearer Token' (read-only beacon credential display, was matching api_key regex via parser label-accumulation). Form-button visibility: per-service-add hides when form is open so test's button-text fallback resolves to per-service-save.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_per_service_editor.py --timeout=90 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================== 5 passed, 1 warning in 98.21s (0:01:38) ====================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_configure_page_http.py --timeout=30 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 5 passed, 1 warning in 15.58s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_runner.py saturn/tests/test_identity.py saturn/tests/test_known_nodes.py saturn/tests/test_resolve_trust_rebind.py saturn/tests/test_admin_config_qj5_13.py saturn/tests/test_boot_validators.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================= 146 passed, 2 warnings in 165.23s (0:02:45) ==================
```
