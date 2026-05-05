# Saturn-pcj / cbt.6.userspace (= cbt.6.1) — UserspaceBackend uses routable_addrs

*2026-05-05T06:00:21Z by Showboat 0.6.1*
<!-- showboat-id: 99c773c5-8a6f-48eb-bb33-c7e5db039b22 -->

Red. Per geoff PARITY_REVIEW_MAY05.md cbt.6.1: userspace.py:121-138 still calls get_lan_ip() then addr=[inet_aton(host_ip)] (single address). Test injects routable_addrs=['192.168.50.10','192.168.60.10']; current ServiceInfo.addresses only carries the single host get_lan_ip resolves to (['192.168.1.13']). Wire-in absent.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_userspace_multi_addr_cbt6_userspace.py --no-header -rN --tb=line 2>&1 | tail -8
```

```output
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 2.08s =========================
```
