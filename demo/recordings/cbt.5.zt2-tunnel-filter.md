# cbt.5 / Saturn-zt2 — filter VPN/tunnel/container ifaces from isolation probe

**Bead:** Saturn-zt2   **Commit:** `0709ad6`

`isolation._link_ifaces()` was returning every UP interface, which
meant `/api/discover.isolation.ifaces_with_link` leaked tunnel / VPN /
container interfaces to whatever caller asked. Two problems:

  1. Information disclosure — admin-token holders or stolen-creds
     attackers could enumerate the VPN posture of a Saturn host.
  2. Decision pollution — the AP-isolation heuristic counted a `utun`
     pseudo-interface as "link present", masking real isolation.

Fix: `TUNNEL_PREFIXES = ('tun', 'utun', 'wg', 'tap', 'docker', 'veth',
'ipsec', 'gif', 'stf')`; skip on prefix match. cbt.5 isolation unit
tests still green; the matrix in
[`cbt.5-isolation-probe.md`](cbt.5-isolation-probe.md) is unchanged
from the caller's perspective — `ifaces_with_link` just no longer
contains pseudo-NICs.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_iface_tunnel_leak_zt2.py
```

## Captured output

```text
saturn/tests/test_iface_tunnel_leak_zt2.py::
test_link_ifaces_excludes_tunnels_and_vpn PASSED                          [100%]
========================= 1 passed in <Ns> ============================
```
