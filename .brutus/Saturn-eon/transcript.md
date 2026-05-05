# Saturn-eon / cbt.4.sec.api_base — sanitize ALL TXT values

*2026-05-05T07:40:53Z by Showboat 0.6.1*
<!-- showboat-id: 7827fdf2-9a2e-4825-b0cf-78d624ce225e -->

Red. _sanitize_txt_value applied only to models. api_base, api_type, deployment, cost pass through with control chars intact. 4 hostile parametrize fields fail; safe-content sanity passes.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_txt_sanitize_all_eon.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
==================== 4 failed, 1 passed, 1 warning in 0.04s ====================
```
