# qj5.6 edit-sent-message — red phase

*2026-05-04T20:32:54Z by Showboat 0.6.1*
<!-- showboat-id: 7aa28071-d677-4dce-b34d-032ab4256233 -->

Spec: each .msg.user surfaces a discoverable Edit affordance; clicking it reveals an editable input populated with the original text. Truncate-and-regenerate end-to-end (real Ollama) verified by demo via tests/harness + rodney capture per scaffold — outside this contract's pytest surface for reliability.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_chat_ux_qj5_6.py --timeout=60 -v 2>&1 | tail -15
```

```output
E       AssertionError: no Edit button to click inside .msg.user
E       assert False

saturn/tests/test_chat_ux_qj5_6.py:131: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_chat_ux_qj5_6.py::test_user_message_has_edit_affordance
FAILED saturn/tests/test_chat_ux_qj5_6.py::test_clicking_edit_reveals_editable_input_with_original_text
======================== 2 failed, 1 warning in 12.94s =========================
```
