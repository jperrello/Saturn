# Saturn-cbt.6 / §17.G.2 — routable_addrs()

*2026-05-05T05:13:04Z by Showboat 0.6.1*
<!-- showboat-id: 416bb555-c1c6-4b1c-ac34-e5e991a7464c -->

Red. saturn/mdns/interfaces.py does not exist. 3 tests pin (1) returns list of valid IPv4 strings, (2) excludes loopback + link-local, (3) finds >=1 on typical dev machine. Userspace ServiceInfo integration deferred to cbt.6.userspace.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_routable_addrs_cbt6.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 failed, 1 warning in 0.06s =========================
```
