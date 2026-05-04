# qj5.13 GREEN — admin_config schema lift (server-side commit 1) + .13.1 + .13.2

*2026-05-04T21:27:21Z by Showboat 0.6.1*
<!-- showboat-id: 3f986a7b-e48b-43b5-87c1-be241fd77c3e -->

Three coupled landings in one commit (same web.py file context). qj5.13 commit-1 (server-side schema lift): AdminConfig extended to 25 fields (legacy 3 + 22 new across CONFIG_FIELDS A.2-A.8) with model_config=ConfigDict(extra='forbid'); validate_admin_config(cfg)->List[str] runs every CONFIG_FIELDS §C rule (CIDR/IP/UUID parses, range bounds, dev-mode gates for trust_mode=open and cors wildcards, proxy_models_method allowlist, budget_period allowlist); apply_admin_config(cfg) fan-outs runtime-effective fields to RATE_RPM/_TPM/_CONCURRENT_PER_IP globals + clears live buckets so next request honours new caps; trust_mode + trusted_node_ids continue to fan-out via _apply_trust_policy. _admin_config_path() now honors SATURN_DATA_DIR. Lifespan boot calls apply_admin_config(_load_admin_config()) so disk values land at startup. POST /api/admin/config validates merged-cfg → 422 with errors[] on violation, 200 + applies on success. qj5.16.13.1 (TrustRebindError surface): saturn/mdns/known_nodes.py:record_rejection gained expected_node_id field; new latest_rejection(name); _resolve in saturn/web.py now raises HTTPException(403, detail={error,service,expected_prefix,seen_prefix,seen_host,remediation}) when rejection on record AND service unresolvable, preserving 404 otherwise. qj5.16.13.2 (live reclassify wiring): _discovered entries now carry node_id; new _reclassify_discovered() drops cached entries whose trust verdict is non-selectable; called from apply_admin_config + after attest/forget so admin policy mutations take effect immediately without waiting for mDNS TTL. Bonus: known_nodes.load() no longer mode-gates (previously refused wide-mode reads); known_node_id() (TOFU pin lookup) keeps mode-gate so test_file_mode_refusal stays green; latest_rejection() reads always so the 403 path works against any operator-readable file.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_admin_config_qj5_13.py --timeout=60 2>&1 | tail -5
```

```output
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 33 passed, 1 warning in 167.70s (0:02:47) ===================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_resolve_trust_rebind.py saturn/tests/test_known_nodes.py --timeout=30 -v 2>&1 | tail -15
```

```output
saturn/tests/test_known_nodes.py::test_lower_priority_rebind_still_rejected PASSED [ 54%]
saturn/tests/test_known_nodes.py::test_allowlist_mode PASSED             [ 63%]
saturn/tests/test_known_nodes.py::test_attest_path PASSED                [ 72%]
saturn/tests/test_known_nodes.py::test_mode_flip_live_update PASSED      [ 81%]
saturn/tests/test_known_nodes.py::test_file_mode_refusal PASSED          [ 90%]
saturn/tests/test_known_nodes.py::test_concurrency_pin_idempotent PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 11 passed, 1 warning in 3.57s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_runner.py saturn/tests/test_identity.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 75 passed, 2 warnings in 15.54s ========================
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
