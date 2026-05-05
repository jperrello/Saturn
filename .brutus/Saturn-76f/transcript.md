# Saturn-76f / cbt.7.prefer — SATURN_PREFER_V6

*2026-05-05T05:57:05Z by Showboat 0.6.1*
<!-- showboat-id: 9640232e-6237-431d-9b3e-5c89f90aeabb -->

Red. saturn.discovery.connect_address does not exist. 3 tests pin (default→v4, prefer_v6→v6, prefer_v6 no-v6→fallback v4).

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_prefer_v6_cbt7_prefer.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 failed, 1 warning in 0.18s =========================
```
