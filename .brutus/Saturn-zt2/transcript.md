# Saturn-zt2 / cbt.5.1.tunnel-leak — filter VPN/tunnel from ifaces_with_link

*2026-05-05T07:16:02Z by Showboat 0.6.1*
<!-- showboat-id: caf46561-70e6-46b4-ac1c-8b97075eaae0 -->

Red. _link_ifaces() returns tun0/utun3/wg0/tap0/docker0/veth*/ipsec0/gif0 — all leak via /api/discover.isolation.ifaces_with_link. Synthetic-interfaces test asserts only en0 survives the filter.

```bash
export PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" && cd /Users/jperr/Documents/Saturn && python -m pytest saturn/tests/test_iface_tunnel_leak_zt2.py --no-header -rN --tb=line 2>&1 | tail -6
```

```output
  /Users/jperr/Documents/Saturn/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1428: PytestConfigWarning: Unknown config option: asyncio_mode
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 failed, 1 warning in 0.08s =========================
```
