# CONTRACT — Saturn-zt2 / cbt.5.1.tunnel-leak: filter VPN/tunnel/container interfaces from `ifaces_with_link`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.
**Geoff cite:** security-audit follow-up to Saturn-5yh (cbt.5.1).
**Parent:** Saturn-5yh.

## Spec restatement (falsifiable)

`saturn/mdns/isolation._link_ifaces()` (line 23-33) returns every UP
interface name (except loopback) verbatim. The list is then exposed via
`/api/discover.isolation.ifaces_with_link` to anyone who can hit the
endpoint (no auth gate today). This leaks the host's VPN / tunnel /
container topology.

Filter MUST drop interface names matching any of these prefixes/patterns:

  - `tun*`  (OpenVPN, generic TUN)
  - `utun*` (macOS userspace tunnels — Tailscale, IKEv2, etc.)
  - `wg*`   (WireGuard)
  - `tap*`  (TAP devices)
  - `docker*` (Docker bridges)
  - `veth*` (virtual ethernet pairs)
  - `ipsec*` (IPSec)
  - `gif*`, `stf*` (BSD tunnels)

## Test files

- `saturn/tests/test_iface_tunnel_leak_zt2.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_iface_tunnel_leak_zt2.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 0.15s
_link_ifaces() must filter tunnel/VPN/container interfaces; leaked:
['tun0','utun3','wg0','tap0','docker0','docker_gwbridge','veth1234abcd','ipsec0','gif0']
```

Transcript: `.brutus/Saturn-zt2/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| Tunnel/VPN/container names | NONE in result (`tun0`, `utun3`, `wg0`, `tap0`, `docker0`, `docker_gwbridge`, `veth*`, `ipsec0`, `gif0`) |
| Legitimate physical | `en0` IN result |

## Fix sketch (non-binding)

```python
# saturn/mdns/isolation.py:23-33
TUNNEL_PREFIXES = ("tun", "utun", "wg", "tap", "docker", "veth",
                   "ipsec", "gif", "stf")

def _link_ifaces() -> List[str]:
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for name, st in psutil.net_if_stats().items():
        if not st.isup:
            continue
        if name == "lo0" or name.startswith("lo"):
            continue
        if any(name.startswith(p) for p in TUNNEL_PREFIXES):
            continue
        out.append(name)
    return out
```

## Out of scope

- Auth gate on `/api/discover` itself — separate concern; if Joey wants
  the whole endpoint authed, file as **Saturn-zt2.auth**. The brief
  filter here is the cheaper fix and matches geoff's recommendation.
- Per-interface allowlist (only Wi-Fi/Ethernet card names). Too tight;
  many laptops have valid `en1`, `eth0`, exotic NIC names. Prefix-blocklist
  for tunnels is the right shape.
- Counting tunnel interfaces in `ifaces_with_link` count without exposing
  names. File as **Saturn-zt2.count** if a numeric heartbeat is wanted.
- Filtering tunnels from `routable_addrs()` (cbt.6/cbt.7 advertise side).
  Sibling concern — file as **Saturn-zt2.advertise** if desired (but the
  v6filter Saturn-x9c already drops most tunnel-typical v6 addresses).

## Implementer

athena → hardener. ETA ~5 min.
