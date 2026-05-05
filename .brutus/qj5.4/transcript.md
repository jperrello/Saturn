# qj5.4 + menu replaces 5 unlabeled icons — red phase

*2026-05-04T20:26:29Z by Showboat 0.6.1*
<!-- showboat-id: 0d80ff39-3120-4cea-9d16-b278d6e1bc3e -->

Spec: collapse the 5 .fab buttons in .chat-input-fabs (#file-upload-btn, #thinking-toggle, #export-json, #export-md, #tools-toggle at index.html:380-385) into a single '+' menu next to #send-btn. FINAL items: Attach file/photo, MCP tools/Connectors. No others. Style relocated to qj5.2 popup.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_chat_ux_qj5_4.py --timeout=60 -v 2>&1 | tail -15
```

```output
E       AssertionError: no '+' menu button found in the chat-input area. Visible label '+' (or aria/title 'add menu', 'plus', 'attach menu', 'attachments menu') is required so users discover the affordance.
E       assert False

saturn/tests/test_chat_ux_qj5_4.py:86: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_chat_ux_qj5_4.py::test_chat_input_row_has_single_entry_button
FAILED saturn/tests/test_chat_ux_qj5_4.py::test_plus_menu_reveals_only_final_items
======================== 2 failed, 1 warning in 10.96s =========================
```
