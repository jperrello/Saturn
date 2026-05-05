# Saturn-zd6 — bounded _failover_state (P1 DoS fix from geoff's audit)

*2026-05-05T07:08:59Z by Showboat 0.6.1*
<!-- showboat-id: 06737f8a-7977-45e2-8195-01de99f70bbd -->

Red. _failover_state at saturn/web.py:149 is unbounded plain dict. No MAX_STICKY constant, no STICKY_TTL_S, no eviction. Two tests pin: (1) size cap at MAX_STICKY=10000 default after 10001 inserts; (2) TTL eviction with STICKY_TTL_S monkeypatched to 0.1s.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_failover_state_bounded_zd6.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 2 failed, 1 warning in 1.05s =========================
```
