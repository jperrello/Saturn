# Saturn-an5 / cbt.3.d.sweep — sweep_stale on SaturnDiscovery

*2026-05-05T06:06:49Z by Showboat 0.6.1*
<!-- showboat-id: 4630a1ac-71ab-4915-b89b-aa6afae8e359 -->

Red. SaturnDiscovery has no sweep_stale method. Test adds old + new entries, calls sweep_stale(max_age=0.4), expects only the new one to remain. /v1/health probe is a follow-up (Saturn-an5.probe) cross-cutting cbt.4.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_discovery_sweep_cbt3d_sweep.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 0.70s =========================
```
