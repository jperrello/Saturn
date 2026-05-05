# Saturn-9rv / cbt.7.advertise = cbt.7.2 — advertise-side AAAA records

*2026-05-05T06:04:31Z by Showboat 0.6.1*
<!-- showboat-id: 85d58359-fba9-455c-8de3-15794d6ae744 -->

Red. routable_addrs() doesn't accept family= kwarg, advertiser doesn't pack v6 into ServiceInfo.addresses. Tests pin (1) family kwarg, (2) advertise packs both v4 4-byte and v6 16-byte entries.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_dual_stack_advertise_cbt7_advertise.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 2 failed, 1 warning in 1.98s =========================
```
