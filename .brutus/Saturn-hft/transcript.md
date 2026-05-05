# Saturn-hft Configure page UI render — red phase

*2026-05-04T22:16:06Z by Showboat 0.6.1*
<!-- showboat-id: 59aee117-1381-4b36-91af-26d38349ab9d -->

Spec: PRE_SPECS_B3.md §17.A.5 commit-2. Render the 8-group AdminConfig schema lift on an admin Configure view. Server-side already done in 8b1e54d / 26d20e1 (qj5.13 commit-1 + qj5.14). Falsifiable: 8 group sections render; values populate from /api/admin/config on mount; edit→save round-trips via POST; invalid POST surfaces inline 422 errors per group; qj5.2 chat Settings popup stays separate.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_configure_page_ui.py --timeout=90 -v 2>&1 | tail -15
```

```output

/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/playwright/_impl/_connection.py:559: Error
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_configure_page_ui.py::test_admin_configure_renders_eight_groups
FAILED saturn/tests/test_configure_page_ui.py::test_section_values_populate_from_api
FAILED saturn/tests/test_configure_page_ui.py::test_edit_save_roundtrips - As...
FAILED saturn/tests/test_configure_page_ui.py::test_invalid_value_shows_inline_error
=================== 4 failed, 1 passed, 1 warning in 59.63s ====================
```
