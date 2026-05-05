# Saturn-cbt.7 / §17.G.3 — dual-stack schema

*2026-05-05T05:14:39Z by Showboat 0.6.1*
<!-- showboat-id: 486af016-6890-4e2d-9bd7-0fa9e7d345db -->

Red. ServiceRecord.addresses and SaturnService.{addresses,ipv6} fields are missing. 3 tests pin (1) ServiceRecord schema, (2) SaturnService schema, (3) addresses list accepts dual-stack v4+v6 strings. Per-backend resolve integration deferred to cbt.7.resolve.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_dual_stack_cbt7.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 failed, 1 warning in 0.12s =========================
```
