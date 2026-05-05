# Saturn-93w — TOFU pin-race P1

*2026-05-05T07:38:47Z by Showboat 0.6.1*
<!-- showboat-id: bb4d05e7-15e5-4c2d-bea3-6819da44ae80 -->

Red. saturn.discovery has no ALLOWLIST_PATH; operator has no name→node_id override. 3 tests pin (1) hostile node_id rejected for allowlisted name, (2) matching node_id accepted, (3) allowlist overrides stale TOFU pin (the pin-race outcome).

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_tofu_pin_race_93w.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 warning, 3 errors in 0.04s =========================
```
