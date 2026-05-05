# Saturn-68j / cbt.4.sec.zd6.per_ip — per-IP cap

*2026-05-05T07:52:12Z by Showboat 0.6.1*
<!-- showboat-id: 220388e4-47ae-4916-9d0a-037f0408dc9a -->

Red. saturn.web has no MAX_STICKY_PER_IP and no _set_sticky helper — current call site at web.py:1266 inserts without IP attribution. P3 follow-up to zd6: closes the gap where one IP can spray to MAX_STICKY=10000.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_failover_state_per_ip_cap_68j.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================== 1 failed, 1 skipped, 1 warning in 0.73s ====================
```
