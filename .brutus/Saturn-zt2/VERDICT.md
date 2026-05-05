# VERDICT — Saturn-zt2 / cbt.5.1.tunnel-leak

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `0709ad6`.

```
saturn/tests/test_iface_tunnel_leak_zt2.py — 1 passed
```

`isolation._link_ifaces()` now drops `tun*`, `utun*`, `wg*`, `tap*`,
`docker*`, `veth*`, `ipsec*`, `gif*`, `stf*` — only `en0` survives the
synthetic-interface filter. Geoff's audit finding (VPN/tunnel topology
leak via `/api/discover.isolation.ifaces_with_link`) is closed.

Transcript: `.brutus/Saturn-zt2/transcript.md`.
