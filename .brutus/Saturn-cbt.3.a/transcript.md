# Saturn-cbt.3.a — settle_time plumbing in discover()

*2026-05-05T05:02:01Z by Showboat 0.6.1*
<!-- showboat-id: 54f80576-3737-443c-ab67-5846d7933099 -->

Red phase. settle_time arg on saturn.discovery.discover() is dead code; SettleDetector uses hardcoded 0.5s. Test calls discover(timeout=5.0, settle_time=3.0) with one Zeroconf-advertised service and asserts elapsed >= 2.5s. Currently 0.53s. NO MOCKS, real Zeroconf on loopback.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_discovery_settle_cbt3a.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
ERROR    saturn.mdns.bonjour:bonjour.py:288 Event loop error in browse: [Errno 9] Bad file descriptor
/Users/jperr/Documents/Saturn/saturn/tests/test_discovery_settle_cbt3a.py:75: AssertionError: discover(timeout=5.0, settle_time=3.0) must respect the caller's settle_time and wait at least ~3s after the last add; took 0.51s. This proves settle_time is plumbed through to SettleDetector (saturn/discovery.py:280 → saturn/mdns/settle.py:5).
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 2.83s =========================
```
