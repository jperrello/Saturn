# Saturn-5yh / cbt.5.1 — wire isolation.probe into /api/discover

*2026-05-05T06:02:00Z by Showboat 0.6.1*
<!-- showboat-id: d5096a96-10bc-4e2f-8358-23ee3e8d0f74 -->

Red. /api/discover returns a bare list — never calls isolation.probe(). Per geoff PARITY_REVIEW_MAY05.md cbt.5.1: response must become {services:[...], isolation:{<probe-shaped>}}. Real saturn web subprocess. Web-UI render update is cbt.5.1.ui (bombadil).

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_api_discover_isolation_cbt5_1.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 8.26s =========================
```
