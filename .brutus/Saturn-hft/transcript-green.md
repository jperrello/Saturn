# Saturn-hft GREEN — Configure page render via HTTP+HTML (CONTRACT_v2)

*2026-05-05T00:19:37Z by Showboat 0.6.1*
<!-- showboat-id: 0f07896a-112c-4bf4-b416-27704d0146e8 -->

Per CONTRACT_v2.md (loosened from playwright to urllib+html.parser per geoff's snapshot). 5/5 v2 tests green. Implementation: (a) Web-UI/index.html renders 8 fieldsets with ac-<field> ids covering CONFIG_FIELDS A.1-A.8 (legends carry the group keywords; AC_FIELDS in app.js drives load+save+inline 422 errors with sessionStorage admin token); (b) NEW /admin/configure route in saturn/web.py extracts the admin-configure-page section out of index.html, server-renders current AdminConfig values as value="…" attributes for every ac-<field> input via _load_admin_config() + regex substitution, wraps the section in a minimal HTML shell that pulls /styles.css + /app.js so the SPA layer hydrates on top — but the value pre-fill is server-side, surviving no-JS reads; (c) admin-configure route gated by Depends(require_admin); (d) chat-tab index.html stays clean of admin-schema input ids (qj5.2 popup separation regression guard). Dropped: v1 playwright fight (was burning context on Execution-context-destroyed race); _ADMIN_CONFIGURE_HTML standalone block; Location.prototype.pathname override hijack from index.html. Field-def drift: 2 sources (AdminConfig.model_fields server schema + Web-UI/app.js AC_FIELDS for client-side load/save) — acceptable per snapshot guidance.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_configure_page_http.py --timeout=30 -v 2>&1 | tail -10
```

```output
saturn/tests/test_configure_page_http.py::test_chat_index_html_does_not_carry_admin_schema_ids PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 5 passed, 1 warning in 15.92s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_runner.py saturn/tests/test_identity.py saturn/tests/test_known_nodes.py saturn/tests/test_resolve_trust_rebind.py saturn/tests/test_admin_config_qj5_13.py saturn/tests/test_boot_validators.py saturn/tests/test_config_honoured.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============ 150 passed, 1 skipped, 2 warnings in 183.26s (0:03:03) ============
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
