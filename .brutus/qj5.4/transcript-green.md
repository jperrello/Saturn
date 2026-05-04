# qj5.4 GREEN — 5 fab icons collapsed into single + menu (Attach + MCP)

*2026-05-04T20:36:37Z by Showboat 0.6.1*
<!-- showboat-id: a9a83cb2-a201-4d29-bf2d-c5bd4df9c647 -->

Implementation: (a) .chat-input-fabs reduced from 5 unlabeled FABs (#file-upload-btn/#thinking-toggle/#export-json/#export-md/#tools-toggle) to a single visible-text '+' button (#plus-menu-btn). (b) New #plus-menu container is positioned absolute next to send-btn with exactly two role=menuitem buttons: 'Attach file/photo' (triggers existing #file-input via fileInput.click()) and 'MCP tools / Connectors' (forwards to #tools-toggle.click() → opens qj5.3 MCP popup). (c) #tools-toggle relocated from .chat-input-fabs to .strip-right (next to Settings) so qj5.3's visible-MCP-text invariant in #chat-shell button still holds. (d) JS null-guarded fileBtn.addEventListener, export-json/-md handlers (so removed elements don't throw). (e) Outside-click dismisses the + menu. Thinking-toggle and export-json/md JS handlers retained but unreachable; if 'thinking' resurfaces it's a separate bead per contract scope.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_4.py --timeout=60 -v 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 2 passed, 1 warning in 15.70s =========================
```

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_chat_ux_qj5_2.py saturn/tests/test_chat_ux_qj5_3.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 69 passed, 2 warnings in 59.44s ========================
```
