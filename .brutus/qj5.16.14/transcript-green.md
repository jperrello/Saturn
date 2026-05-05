# qj5.16.14 GREEN — beacon sleep transition + power-mgmt opt-in + §7.5 budget plumbing co-land

*2026-05-05T03:25:30Z by Showboat 0.6.1*
<!-- showboat-id: 059c104a-6b4c-46fb-9dbb-c480d4738af2 -->

11/11 contract tests + §7.5 beacon-budget plumbing co-landed per geoff §17.E.9. Implementation: (1) NEW saturn/mdns/sleep.py — KeepAwake (caffeinate -i -w <ppid> on Darwin / systemd-inhibit --what=sleep --who=saturn on Linux; process-tree-bound, parent-crash kills child within 5s; noop on unsupported platforms); SleepWatcher (pyobjc / jeepney import-guarded; _dispatch_for_test seam for callback ordering invariant; noop without binding). (2) saturn/runner.py: CredentialManager grew invalidate/needs_remint/mark_fresh + _sleep_invalidated flag. NEW module-level helpers: _beacon_on_sleep (unregister + invalidate), _beacon_on_wake (create → mark_fresh → re_register, in that order so published TXT carries fresh credential), _rotation_tick (monotonic-jump > 2× rotation_interval forces re-mint), _warn_no_sleep_handling (single warning citing §16 with both remediations), _prompt_keep_awake (tomllib parse + naive [beacon] block edit; persists keep_awake + keep_awake_decided so subsequent runs don't re-prompt). (3) §7.5 beacon-budget plumbing co-land: BeaconConfig grew max_budget_usd / keep_awake / keep_awake_decided / sleep_handling fields; rotation_interval default 300→400 (300/600=2.00 violated 1.5 ceiling; 400/600≈1.5 ok); openrouter.payload accepts max_budget_usd → emits 'limit' field on sub-key mint; deepinfra.revoke now actually DELETEs the scoped JWT (was literal 'pass' — leaked tokens lived full TTL). (4) AdminConfig.beacon_max_budget_usd field + AC_FIELDS row + admin Configure page input + ROUNDTRIP_TABLE entry.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_beacon_sleep.py --timeout=30 -v 2>&1 | tail -15
```

```output
saturn/tests/test_beacon_sleep.py::test_credential_manager_invalidate_marks_remint_needed PASSED [ 54%]
saturn/tests/test_beacon_sleep.py::test_beacon_unregisters_on_sleep_signal PASSED [ 63%]
saturn/tests/test_beacon_sleep.py::test_beacon_remints_on_wake_signal PASSED [ 72%]
saturn/tests/test_beacon_sleep.py::test_rotation_loop_detects_unwitnessed_sleep PASSED [ 81%]
saturn/tests/test_beacon_sleep.py::test_warning_when_no_keepawake_and_no_watcher PASSED [ 90%]
saturn/tests/test_beacon_sleep.py::test_cli_prompt_persists_keep_awake_decision PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 11 passed, 1 warning in 1.39s =========================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_admin_config_qj5_13.py saturn/tests/test_admin_config_drift.py saturn/tests/test_runner_auth.py saturn/tests/test_runner.py saturn/tests/test_identity.py saturn/tests/test_known_nodes.py saturn/tests/test_resolve_trust_rebind.py saturn/tests/test_boot_validators.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py saturn/tests/test_trusted_proxies.py saturn/tests/test_receipt_meta.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============ 159 passed, 1 skipped, 2 warnings in 203.90s (0:03:23) ============
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
