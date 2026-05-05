# Saturn-xqw — api_base SSRF P1

*2026-05-05T07:36:31Z by Showboat 0.6.1*
<!-- showboat-id: 6f776b4c-75d0-43d1-8596-080f85bc9c12 -->

Red. 14/14 hostile api_base vectors flow through SaturnService.effective_endpoint unguarded. AWS metadata, loopback, RFC-1918, CGNAT, IPv6 ULA, IPv6 link-local, javascript: scheme — all pass. Safe https://api.openai.com control passes through preserved.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_api_base_ssrf_xqw.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=================== 14 failed, 1 passed, 1 warning in 0.05s ====================
```
