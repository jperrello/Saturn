# Saturn-1xh / cbt.7.resolve = cbt.7.1 — userspace dual-stack address extraction

*2026-05-05T06:03:23Z by Showboat 0.6.1*
<!-- showboat-id: d9702a93-8fd1-4a8b-ac49-7b532f246d91 -->

Red. userspace _resolve() takes only info.addresses[0] via inet_ntoa (v4-only). Test publishes ServiceInfo with v4+v6 addresses; _resolve must walk all entries and dispatch on len: 4→inet_ntoa, 16→inet_ntop(AF_INET6). Bonjour/Avahi backends are separate sub-beads.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_dual_stack_resolve_cbt7_resolve.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 2.04s =========================
```
