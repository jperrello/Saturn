# Saturn-cbt.3.b — userspace parallel resolves

*2026-05-05T05:08:39Z by Showboat 0.6.1*
<!-- showboat-id: 3425b0d1-9770-4cd4-baab-a2f295d18ca7 -->

Red phase. UserspaceBackend dispatches _resolve from zeroconf's single listener thread. Test registers 12 services, captures thread idents from add callbacks, asserts >=2 distinct threads. Currently 1. Real Zeroconf advertisers + real UserspaceBackend, NO MOCKS.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_userspace_parallel_resolve_cbt3b.py --no-header -rN --tb=line 2>&1 | tail -10
```

```output
     +  where 1 = len({6150041600})
/Users/jperr/Documents/Saturn/saturn/tests/test_userspace_parallel_resolve_cbt3b.py:95: AssertionError: add_service callbacks fired from only 1 thread(s) (idents=[6150041600]). _resolve() blocks the zeroconf engine thread; dispatch resolves to a ThreadPoolExecutor at saturn/mdns/userspace.py:55-63 so concurrent adds run in parallel. Saw 12 adds total.
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 1 failed, 1 warning in 20.28s =========================
```
