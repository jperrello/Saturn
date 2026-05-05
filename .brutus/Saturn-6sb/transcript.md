# Saturn-6sb per-service editor — red phase

*2026-05-04T22:22:05Z by Showboat 0.6.1*
<!-- showboat-id: bdfcbecd-6a93-48f8-9ace-ffcb7bd8a11d -->

Spec: PRE_SPECS_B3.md §17.A.5 commit-3 + CONFIG_FIELDS §B. Per-service editor on the admin Configure view: list existing; create round-trips POST; edit propagates immediately via apply_admin_config path; delete confirms then DELETE; sensitive api_key input must be env-var NAME only (Saturn invariant: configs hold env-var names, never values).

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_per_service_editor.py --timeout=90 2>&1 | tail -10
```

```output
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_per_service_editor.py::test_per_service_editor_lists_existing_services
FAILED saturn/tests/test_per_service_editor.py::test_create_new_service_via_ui_round_trips
FAILED saturn/tests/test_per_service_editor.py::test_edit_service_via_ui_propagates
FAILED saturn/tests/test_per_service_editor.py::test_delete_service_via_ui_confirms_then_removes
FAILED saturn/tests/test_per_service_editor.py::test_sensitive_auth_fields_gated
=================== 5 failed, 1 warning in 71.50s (0:01:11) ====================
```
