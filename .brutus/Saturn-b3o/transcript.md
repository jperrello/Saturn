# Saturn-b3o / cbt.4.sec.ratelimit — /api/system/chat rate-limit regression guard

*2026-05-05T07:02:30Z by Showboat 0.6.1*
<!-- showboat-id: 6c8f1e86-ac0d-404f-b9c5-14cd7b925743 -->

GREEN on first run. _check_rate() is already wired into brutus_chat at saturn/web.py:1065 — no missing behavior. This is a preserve-behavior regression-guard contract per house rules. Pins the invariant so a future refactor cannot silently drop the gate.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_system_chat_ratelimit_b3o.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 passed, 1 warning in 2.55s =========================
```
