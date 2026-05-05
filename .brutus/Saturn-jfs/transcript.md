# Saturn-jfs / cbt.5.1.probe-dos — /api/discover rate limit

*2026-05-05T07:42:44Z by Showboat 0.6.1*
<!-- showboat-id: 70765d12-75db-4b3f-8fc2-8fc38fcd3c01 -->

Red. /api/discover at saturn/web.py:661-683 has no _check_rate gate. Each request blocks 9s on discover()+isolation.probe(). 6 rapid GETs at SATURN_RATE_RPM=2 yields no 429s — should yield ≥3. Test took 44s wall, demonstrating the amplification: 6 attacker requests = 54s of process-time.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_api_discover_ratelimit_jfs.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 failed, 1 warning in 43.91s =========================
```
