# qj5.3 MCP TOOLS popup + add-server flow — red phase

*2026-05-04T20:23:37Z by Showboat 0.6.1*
<!-- showboat-id: 7c29b1b6-9b9c-4acb-9254-c3e4d6c1f401 -->

Spec: move MCP tools list (today inline #tools-panel, index.html:314) into a positioned popup mirroring qj5.2 pattern. Surface an obvious 'Add MCP server' affordance directly inside the popup — no two-click 'Servers' detour through #tools-manage. MCP entry button must show visible 'MCP'/'Tools' text.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_chat_ux_qj5_3.py --timeout=60 -v 2>&1 | tail -15
```

```output
E       AssertionError: after MCP click, no positioned (absolute/fixed) popup surfaces a discoverable 'Add MCP server' / '+ MCP server' / 'New MCP …' affordance directly. The current #tools-panel is inline (not positioned) and hides the add form behind a 'Servers' button.
E       assert None is not None

saturn/tests/test_chat_ux_qj5_3.py:115: AssertionError
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_chat_ux_qj5_3.py::test_mcp_entry_button_has_visible_label
FAILED saturn/tests/test_chat_ux_qj5_3.py::test_mcp_click_reveals_popup_with_add_server
======================== 2 failed, 1 warning in 18.81s =========================
```
