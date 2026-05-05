# Saturn-bfx / cbt.8.integrate — advertiser TXT validate + mtrunc

*2026-05-05T05:58:22Z by Showboat 0.6.1*
<!-- showboat-id: fa5d0cc0-cf5b-4792-b620-b779f92aaf39 -->

Red. _properties() doesn't prune capabilities/features under bloat; register() doesn't raise TxtTooLarge on unprunable bloat — silently logs and ships oversized TXT.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_advertise_mtrunc_cbt8_integrate.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 2 failed, 1 warning in 0.25s =========================
```

Green. Hardener landed in 6df7367. _properties() now self-prunes capabilities (mtrunc=1); register() raises TxtTooLarge on unprunable bloat. cbt.8 unit tests preserved (validate-under-ceiling/individual/total).

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_advertise_mtrunc_cbt8_integrate.py saturn/tests/test_txt_validate_cbt8.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 5 passed, 1 warning in 0.17s =========================
```
