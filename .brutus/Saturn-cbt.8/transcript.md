# Saturn-cbt.8 / §17.G.4 — TXT validation

*2026-05-05T05:10:33Z by Showboat 0.6.1*
<!-- showboat-id: 52e87714-f255-429e-b9b7-34f624cc817d -->

Red phase. saturn/mdns/txt.py does not exist. 3 failing tests pin the validator's three discriminating cases (under-ceiling returns int; oversized individual entry raises with key/255 hint; oversized total raises with ceiling/total hint).

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_txt_validate_cbt8.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 3 failed, 1 warning in 0.03s =========================
```
