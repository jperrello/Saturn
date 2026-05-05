# qj5.16.13.3 pin-after-settle race — red phase

*2026-05-04T22:26:46Z by Showboat 0.6.1*
<!-- showboat-id: 4c9f6ad4-7dd0-4048-a5fd-6f9b115a4989 -->

Spec: SECURITY_AUDIT.md §15.2.b + §15.7. Defer known_nodes.pin() in saturn/discovery.py:_add until SettleDetector signals quiet OR same (name, node_id) seen ≥2 times. Today _add pins immediately, letting an attacker who races a priority-0 advertisement first grab the TOFU slot during fresh-install discovery.

```bash
export PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH; cd /Users/jperr/Documents/Saturn && python3 -m pytest saturn/tests/test_pin_after_settle.py --timeout=30 -v 2>&1 | tail -10
```

```output
  /Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED saturn/tests/test_pin_after_settle.py::test_single_first_seen_does_not_pin_during_settle
FAILED saturn/tests/test_pin_after_settle.py::test_competing_node_ids_in_settle_window_block_pin
FAILED saturn/tests/test_pin_after_settle.py::test_attacker_first_does_not_grab_pin
==================== 3 failed, 2 passed, 1 warning in 0.27s ====================
```
