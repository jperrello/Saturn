# qj5.16.13 GREEN — TOFU node_id pinning + admin allowlist (commits 1+2)

*2026-05-04T21:01:54Z by Showboat 0.6.1*
<!-- showboat-id: b1e200ab-9ee1-4236-8579-bf0fa0d836e5 -->

Implementation per SECURITY_AUDIT §15. Commit 1 (TOFU core): saturn/mdns/known_nodes.py with atomic 0600-mode JSON store at ~/.saturn/known_nodes.json (load/save/known_node_id/pin/record_rejection/attest/forget); SaturnService.trust field; module-level _trust_mode/_allowlist + set_trust_policy(); _classify_trust(); _add wires classify → pin/record_rejection; get_best_service/get_all_services filter to selectable trust set; reclassify_all() for live mode flips; TrustRebindError exception. Selection rule: open mode → all selectable; otherwise trust ∈ {pinned, first_seen, allowlist}. Commit 2 (admin wiring): AdminConfig extended with trust_mode + trusted_node_ids (UUID validation, 422 on bad shape); _apply_trust_policy() on boot lifespan + on POST /api/admin/config; new endpoints GET /api/admin/known-nodes + POST /api/admin/known-nodes/attest + POST /api/admin/known-nodes/forget all behind require_admin. SaturnDiscovery.__init__ now accepts backend=None|False for unit-test isolation. Commit 3 (UI Configure-page) deferred per athena's 'commits 1+2 first, 3 if time-tight' guidance.

```bash
python3 -m pytest saturn/tests/test_known_nodes.py -v 2>&1 | tail -12
```

```output
saturn/tests/test_known_nodes.py::test_mode_flip_live_update PASSED      [ 75%]
saturn/tests/test_known_nodes.py::test_file_mode_refusal PASSED          [ 87%]
saturn/tests/test_known_nodes.py::test_concurrency_pin_idempotent PASSED [100%]

=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 8 passed, 1 warning in 0.10s =========================
```

```bash
python3 -m pytest saturn/tests/test_runner.py saturn/tests/test_identity.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 75 passed, 2 warnings in 17.33s ========================
```

```bash
python3 -m tests.harness.selftest 2>&1 | tail -3
```

```output
OK: revoked subkey

[selftest] ALL OK
```
