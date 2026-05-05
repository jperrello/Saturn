# Saturn-vyy / cbt.cross-client.real — protocol-level cross-client

*2026-05-05T07:33:49Z by Showboat 0.6.1*
<!-- showboat-id: f9931790-1a47-4671-954a-11e92efbdd72 -->

GREEN on first run. Regression guard proving Saturn=protocol. Real SaturnAdvertiser registered; Python zeroconf, dns-sd subprocess (macOS Bonjour reference), and curl all observe the service. NO MOCKS. macOS-only via dns-sd; Linux variant filed as Saturn-vyy.linux.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_cross_client_real_vyy.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 passed, 1 warning in 5.25s =========================
```
