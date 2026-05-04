# qj5.6 GREEN — edit affordance + editable input on .msg.user

*2026-05-04T20:42:30Z by Showboat 0.6.1*
<!-- showboat-id: ec5e89f5-d20c-458c-842a-e4d8662bf9d2 -->

Implementation: delegated 'mouseover' on document ensures every .msg.user (including dynamically rendered or test-fixture-injected) gets an Edit button via ensureEditAffordance; MutationObserver on #messages catches new ones; initial walk seeds existing. Click on .edit-btn replaces .bubble with a textarea pre-populated from textContent + Save/Cancel actions. Save: replaces textarea back to .bubble with new text, removes all subsequent .msg siblings, prunes chats[activeChat].messages to truncation index, and re-runs send(input.value=newText) — wired but acceptance #5 (truncate-and-regenerate against real Ollama + DOM diff) is gated to demo per contract scope. Cancel reverts. CSS: edit button hover-revealed with low-opacity → 1 on hover/focus; textarea + actions styled in qj5.x family.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_6.py --timeout=60 -v 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 2 passed, 1 warning in 16.68s =========================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_chat_ux_qj5_2.py saturn/tests/test_chat_ux_qj5_3.py saturn/tests/test_chat_ux_qj5_4.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 71 passed, 2 warnings in 76.41s (0:01:16) ===================
```
