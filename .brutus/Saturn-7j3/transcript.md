# Saturn-7j3 known-nodes UI — red phase

*2026-05-04T22:30:36Z by Showboat 0.6.1*
<!-- showboat-id: 46d200e3-f669-4f87-9f4e-aa59ad26d461 -->

Spec: SECURITY_AUDIT.md §15.6 deferred commit-3. UI render of trust-mode dropdown + allowlist editor + pending-rejections table on the admin Configure view. Server-side endpoints (GET /api/admin/known-nodes, POST .../attest, POST .../forget) shipped + 401-gated by qj5.16.13.1+.2.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_known_nodes_ui.py --timeout=90 2>&1 | tail -10
```

```output
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_known_nodes_ui.py::test_trust_mode_dropdown_has_three_options
FAILED saturn/tests/test_known_nodes_ui.py::test_allowlist_picker_lists_known_nodes
FAILED saturn/tests/test_known_nodes_ui.py::test_rejections_table_renders_prefixes_and_actions
=================== 3 failed, 3 passed, 1 warning in 41.30s ====================
```
