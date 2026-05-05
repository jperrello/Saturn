# Saturn-x9c / cbt.7.advertise.v6filter — ULA/6to4/Teredo/mixed-case-fe80 filter gaps

*2026-05-05T07:14:41Z by Showboat 0.6.1*
<!-- showboat-id: 2f5d8d07-1bd5-4cf5-9521-52e8cf80fd75 -->

Red. interfaces.py:24-28 only filters ::1, :: and fe80/FE80. Test injects synthetic v6 addrs covering fc00::/7, fd00::/7, 2002::/16, 2001::/32, Fe80 (mixed case) plus a legitimate global. All disallowed must be dropped; global must be kept.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_v6_filter_gaps_x9c.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 0.05s =========================
```
