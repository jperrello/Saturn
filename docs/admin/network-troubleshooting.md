# Network troubleshooting — operator guide

For operators when peers don't appear, only-one-side sees the other, or `saturn serve` won't start. The four edges below are the failure modes Saturn now detects or works around — `cbt.5–cbt.8` from MAY05.

If you don't know where to start, run the [§First-pass probe](#first-pass-probe).

## First-pass probe

Run this from any host that should be participating in discovery:

```bash
python3 -c "from saturn.mdns.isolation import probe; r = probe(); print(r)"
```

Output is one `IsolationProbe` line. Read it left-to-right:

| Field | Healthy | Notes |
|---|---|---|
| `advertising` | `True` | `False` means the local zeroconf engine refused to register — usually a port-bind issue. See `diagnosis`. |
| `self_seen` | `True` | Round-tripped the probe through the local stack. `False` with `advertising=True` is multicast trouble. |
| `peers_seen` | ≥ 0 | Counts other `_saturn-probe._tcp.local.` advertisers running the probe at the same time. Often 0 in normal operation. |
| `ifaces_with_link` | ≥ 1 | Empty means `psutil.net_if_stats()` reports no UP interfaces. |
| `suspected_ap_isolation` | `False` | When `True`, see [§AP isolation](#ap-isolation). |
| `diagnosis` | `"loopback healthy"` | Free-text; the human-readable summary. |

Decision tree:

- `suspected_ap_isolation=True` → [§AP isolation](#ap-isolation).
- `self_seen=False, advertising=True, ifaces_with_link>=1` → loopback multicast is broken. Check host firewall (macOS Application Firewall, Linux `iptables -L INPUT`, Windows Defender Firewall). Saturn cannot work around this.
- `self_seen=False, ifaces_with_link=0` → no network. Bring an interface up before going further.
- All green but Saturn clients still don't see your server → keep going to [§Multi-interface](#multi-interface) or [§Large TXT](#large-txt).

The probe lives at `saturn/mdns/isolation.py:36`. It runs in ~4s by default; pass `timeout=` if you need to be patient.

## AP isolation

**Symptom:** "I'm advertising, my colleague is advertising, neither of us sees the other. Both of us are on the same Wi-Fi."

**Cause:** the access point is dropping client-to-client traffic. This is the default on:

- Most university guest networks (eduroam at many sites, UCSC-Guest, etc.).
- Hotel and airport Wi-Fi.
- Any AP with "client isolation" / "AP isolation" / "P2P blocking" enabled.
- Some enterprise networks where the security team turned multicast filtering on without telling anyone.

**Detection:** `probe()` returns `suspected_ap_isolation=True` when:

- The probe's own service round-trips locally (`self_seen=True`), **and**
- No peers respond (`peers_seen=0`), **and**
- At least one non-loopback interface is UP (`ifaces_with_link>=1`).

This combination means "the local stack works, the network is up, but multicast doesn't reach beyond this host." That is AP isolation by definition.

The Web-UI Network Scan tab consumes this signal automatically. When `/api/discover` returns `isolation.suspected_ap_isolation=True`, the scan card is replaced with a red-tinted diagnosis + a one-click manual-config CTA.

**There is no fix from Saturn's side.** Your options:

1. **Move to a network that doesn't isolate.** A wired switch or a home/office AP with isolation off.
2. **Use manual config.** Point each client at a known server `host:port` in the Configure page. Saturn will skip discovery and connect directly.
3. **Tunnel.** If you control one host on the isolated network and one outside, run a tunnel (Tailscale, WireGuard) so the participating hosts are on a network that allows multicast — or accept manual-config addressing across the tunnel.

**What not to try:** asking the AP admin to "enable mDNS" without specifying *client-to-client multicast forwarding*. Many enterprise APs have multiple knobs; the wrong one stays off.

Reference: `saturn/mdns/isolation.py:99-101`. Pre-spec: `PRE_SPECS_B3.md §17.G.1`.

## Multi-interface

**Symptom:** "My laptop has Wi-Fi and Ethernet. The server I'm running shows up only for clients on one of the two subnets."

**Cause:** prior to `cbt.6`, Saturn's userspace mDNS backend advertised on a single address — `get_lan_ip()` returns whichever interface holds the default route. Bonjour and Avahi backends were already multi-interface by accident.

**Fix:** `cbt.6` adds `saturn/mdns/interfaces.py:routable_addrs()`, which enumerates every non-loopback, non-link-local IPv4 address on a UP interface. The userspace backend passes the full list to `zeroconf.ServiceInfo(addresses=...)`.

**Verification:**

```bash
python3 -c "from saturn.mdns.interfaces import routable_addrs; print(routable_addrs())"
```

Should return every address you expect to be reachable from your LAN. If it returns one address but `ifconfig`/`ip a` shows two:

- Is the second interface UP? `psutil.net_if_stats()[iface].isup` must be `True`.
- Is the second address link-local (`169.254.*`) or loopback (`127.*`)? Those are filtered out.
- Is the address IPv4? `routable_addrs()` is v4-only today; v6 lands with `cbt.7`.

**Operator knob:** `SATURN_ADVERTISE_ALL` (default `1`). Set `0` to fall back to the legacy single-IP path. There's almost never a reason to.

**Cross-client verification:** from a client on each subnet, run Network Scan against the multi-NIC server. The same `node_id` should appear in both — different `host` (the address visible on each subnet's side), same `id` in TXT.

Reference: `saturn/mdns/interfaces.py:7`. Pre-spec: `PRE_SPECS_B3.md §17.G.2`.

## IPv6 / dual-stack

**Status:** rough-pass shipping; full integration in progress. Read this section as "what to expect" rather than "fully done."

**Symptom (post-cbt.7):** "I want clients on a v6-only or v6-preferred network to find my server."

**Spec:** `ServiceRecord.addresses: List[str]` carries every resolved address — A and AAAA. `SaturnService` exposes `addresses` plus a convenience `ipv6: Optional[str]` (first AAAA, if any).

**Operator knob:** `SATURN_PREFER_V6` (default `0`). When `1`, the client prefers the first AAAA over the first A on connection; falls back to A on connect timeout.

**Dedup:** when the same `node_id` is resolved over both v4 and v6 backends, Saturn collapses it into a single `SaturnService` with both addresses populated. The discovery cache key is `node_id:name`, not address — same node = same entry.

**Common operator issues:**

- **AAAA present but unreachable.** Link-local (`fe80::/10`) addresses don't route across subnets. If `prefer_ipv6=1` and connect fails, Saturn falls back to v4 — but the failover counts as one "active" failure for the purposes of `cbt.4` breakers. Consider leaving `prefer_ipv6=0` on networks with mixed reachability.
- **No AAAA in the receipt.** The OS has IPv6 disabled, or the interface has no v6 address. `ipv6=None` is the documented signal for "v4 only here."
- **Same service listed twice.** Should not happen post-`cbt.7`. If you see it, file a bead with the receipt's `addresses` list.

Reference: `PRE_SPECS_B3.md §17.G.3`. Bead: `Saturn-cbt.7`.

## Large TXT

**Symptom:** `saturn serve` exits with `TxtTooLarge: TXT total <N> bytes exceeds ceiling 1200`.

**Cause:** the TXT record Saturn was about to advertise is bigger than the safe ceiling for unfragmented multicast.

mDNS rides UDP. Multicast packets above the ~1500-byte interface MTU fragment, and many switches and APs drop fragmented multicast silently. Saturn used to build oversize TXT records when the model list grew, and the symptom was "discovery works in dev, fails in prod" — because the dev LAN tolerated fragmentation and the prod LAN didn't.

**Validation:** `saturn/mdns/txt.py:validate(props)` runs before `backend.advertise()`. It enforces:

- Per-entry: any single `key=value` over 255 bytes raises (RFC 6763 §6.1).
- Total: encoded total over `TXT_SAFE_CEILING` (default 1200) raises.

**Pruning order** (`SaturnAdvertiser.register()`): truncate `models` first, then `capabilities`, then `features`, set `mtrunc=1`. If even minimal pruning can't fit, register fails loudly.

**Operator knob:** `SATURN_TXT_CEILING` (default `1200`). Raise only if you are confident the entire path between Saturn peers supports unfragmented packets larger than 1500 bytes — i.e. you control the network end-to-end and have configured jumbo frames everywhere. On the public internet, on Wi-Fi, on most LANs — leave it alone.

**What to do when it fires:**

- Read the byte count in the error. Saturn names the total or the offending entry.
- The usual culprit is `models`. Trim the runner's advertised model list, or accept truncation (`mtrunc=1` is honored by Saturn clients).
- A capability with a long opaque blob is almost always misconfiguration; capabilities should be short tags like `streaming`, `tools`, `vision`.
- If you raise the ceiling, document why — future operators will assume the default and be confused.

Reference: `saturn/mdns/txt.py`. Commit: `173ad9e` (cbt.8). Pre-spec: `PRE_SPECS_B3.md §17.G.4`.

## When to give up on discovery

Discovery is a convenience, not a requirement. Saturn supports manual config from the Configure page (`docs/admin/configure.md`) — direct `host:port` for each backend.

Switch to manual config when:

- The probe says `suspected_ap_isolation=True` and you can't change networks.
- You're running across hosts that aren't on the same L2 segment (multicast doesn't cross routers without IGMP snooping configured, which most home gear gets wrong).
- You have a security policy that disallows mDNS.

Manual config bypasses everything in this document. Failover (`cbt.4`) still works against manually configured peers — the candidate set is just populated from config instead of from discovery.

## References

- `saturn/mdns/isolation.py` — AP-isolation probe.
- `saturn/mdns/interfaces.py` — multi-NIC address enumeration.
- `saturn/mdns/txt.py` — TXT validator.
- `DISCOVERY_AUDIT.md` — the four discovery areas as a single audit.
- `PRE_SPECS_B3.md §17.G.{1–4}` — field-level pre-specs for each edge.
- `docs/admin/discovery.md` — how discovery is supposed to work when none of these edges fire.
- `docs/admin/failover.md` — what happens after discovery delivers a candidate set.
