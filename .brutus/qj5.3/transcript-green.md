# qj5.3 GREEN — MCP popup with direct Add-MCP-server affordance

*2026-05-04T20:30:08Z by Showboat 0.6.1*
<!-- showboat-id: 0a78b8ec-5611-4a0d-b6b7-dadacced2bc5 -->

Implementation: (a) #tools-toggle FAB now carries visible 'MCP' text via .fab-text span (Nielsen H6). (b) .tools-panel CSS migrated from inline border-bottom panel to a positioned popup (position: absolute; bottom-right anchored; backdrop-filter blur, matches qj5.2 popup pattern). (c) Removed the #tools-manage 'Servers' detour — #mcp-servers-config no longer 'hidden' by default; the add-server form (renamed 'Add MCP server' header + '+ Add MCP server' button) shows immediately when the popup opens. (d) JS handler that gated the form on tools-manage replaced with refreshMCPServers() trigger when the panel becomes visible.

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_3.py --timeout=60 -v 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
../../../../Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 2 passed, 1 warning in 47.24s =========================
```

```bash
python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_chat_ux_qj5_2.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py 2>&1 | tail -3
```

```output

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 67 passed, 2 warnings in 37.46s ========================
```
