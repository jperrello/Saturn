# Saturn-7sg / cbt.7.dedup — dual-stack address merge

*2026-05-05T06:05:50Z by Showboat 0.6.1*
<!-- showboat-id: 6bc79006-4155-4b98-a9b8-da4e2b1bd98e -->

Red. _add() overwrites self.services[key] on second event — addresses from the first event are lost. Test feeds two events for the same (node_id, name): first v4, then v6. Currently only v6 survives. NO MOCKS.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_dual_stack_dedup_cbt7_dedup.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 0.14s =========================
```
