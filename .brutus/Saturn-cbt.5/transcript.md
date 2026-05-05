# Saturn-cbt.5 / §17.G.1 — AP isolation probe

*2026-05-05T05:11:55Z by Showboat 0.6.1*
<!-- showboat-id: 5bebebe8-a53f-40eb-9f07-bdd64be59585 -->

Red. saturn/mdns/isolation.py does not exist. 2 tests pin (1) module surface (IsolationProbe @dataclass with 6 fields + probe()) and (2) loopback round-trip self_seen=True invariant. Web/UI integration deferred to cbt.5.web.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_isolation_cbt5.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 2 failed, 1 warning in 0.07s =========================
```
