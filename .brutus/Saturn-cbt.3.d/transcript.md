# Saturn-cbt.3.d — last_seen + max_age

*2026-05-05T05:05:58Z by Showboat 0.6.1*
<!-- showboat-id: 80c22166-9b24-471e-905c-0ec7e0dd9fe3 -->

Red phase. SaturnService has no last_seen field; discover() doesn't accept max_age kwarg. Two tests pin both. Real Zeroconf publish on loopback. Liveness-probe sweep (cross-cuts cbt.4) intentionally deferred to cbt.3.d.sweep.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_discovery_max_age_cbt3d.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
E   TypeError: discover() got an unexpected keyword argument 'max_age'
/Users/jperr/Documents/Saturn/saturn/tests/test_discovery_max_age_cbt3d.py:106: TypeError: discover() got an unexpected keyword argument 'max_age'
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 2 failed, 1 warning in 5.07s =========================
```
