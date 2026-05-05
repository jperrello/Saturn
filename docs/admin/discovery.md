# Discovery — operator guide

For operators running Saturn in production. Covers what discovery actually does on the wire, how to tune it, where it stores state, and what to check first when peers don't appear.

If you're paged at 2am because "nobody can find the LLM," start at [§Triage](#triage). If you're standing up a new deployment, read top-to-bottom.

## What discovery is

A Saturn server advertises one mDNS service per LAN — type `_saturn._tcp.local.` — with a TXT record carrying its `node_id`, advertised models, priority, and capabilities. Saturn clients browse the same type and pick the lowest-priority healthy peer that advertises the requested model.

The discovery code lives in `saturn/discovery.py` and `saturn/mdns/`. The transport is platform-dependent (Bonjour on macOS, Avahi on Linux when present, Python `zeroconf` userspace fallback otherwise) but the wire protocol is identical — RFC 6762 (mDNS) + RFC 6763 (DNS-SD).

## Settle detection

`discover()` (`saturn/discovery.py:280`) blocks until either:

- The discovery cache has been quiet for `settle_time` seconds (default `1.0`) — no new `added`/`updated` events arriving — **or**
- The hard `timeout` (default `8.0`) elapses.

`settle_time` is plumbed into `SettleDetector` since `cbt.3.a` (`75c58f9`) — earlier versions silently ignored it. If you previously tuned settle and saw no effect, that bug is fixed. Re-tune.

**Tuning rules:**

- **Quiet LAN, fast clients:** `settle_time=0.3` returns ~300ms after the first peer is seen. Good for the Web-UI Network Scan button.
- **Noisy LAN with churn (>2 advertise/sec):** the quiet window never opens; `discover()` returns at `timeout` with whatever is in the cache. Treat that as "this LAN is unstable, snapshot is best-effort." Don't lower `timeout` below 2s on a known-noisy network.
- **Discovery from a script:** pass an explicit `timeout` and `settle_time`. The defaults are tuned for interactive UI, not batch jobs.

Removals do **not** reset the settle timer (`saturn/discovery.py:282`); only adds. A peer disappearing mid-scan won't extend the wait.

## known_nodes.json — the trust file

Path: `~/.saturn/known_nodes.json`. Structure:

```json
{
  "trusted": {"<service-name>": {"node_id": "<uuid>", "host": "...", "last_seen": <ts>}},
  "rejected": [{"name": "...", "node_id": "...", "reason": "rebind_attempt", ...}]
}
```

This is Saturn's TOFU (trust-on-first-use) ledger. `cbt.3.c` (`8d2bbfd`) added a `fcntl.flock` around the load+save cycle so two Saturn processes on the same host (e.g., a server and a client) can't race-corrupt the file. Single-host clusters are now safe; the file is still intended to be **per-user**, not shared via NFS.

**Pin gating:** since `qj5.16.13.3` (`500f576`), Saturn defers pinning a `node_id` until it has seen the same `(name, node_id)` pair on `PIN_CONFIRMATIONS` consecutive discovery cycles. A single rogue advertisement can no longer claim a name. Operators who want stricter posture: switch `trust_mode` to `allowlist` and pre-populate `trusted` from the Configure page.

**Rejections:** mismatch between discovered `node_id` and pinned value lands in `rejected[]` with `reason="rebind_attempt"` and surfaces on the Configure page §A.8 known-nodes panel. Investigate before approving.

**File hygiene:** `rejected[]` is unbounded today — DISCOVERY_AUDIT.md (c) flagged this; a follow-up bead caps it. If you see runaway growth, a flapping peer is the cause; track it down rather than truncating the file.

## max_age — zombie filter

Saturn does not run its own TTL sweep over the cache. Removal is driven by the underlying mDNS library's record TTL (zeroconf default 120s; Bonjour daemon default ~75 minutes for service records) plus goodbye packets. A peer that crashes hard without sending a goodbye persists in the cache until the library expires it.

`cbt.3.d` (`fa57189`) added two surfaces:

- `SaturnService.last_seen: float` (unix seconds) — updated on every `added`/`updated` event.
- `discover(max_age=N)` — drops entries whose `last_seen` is older than `N` seconds before returning.

**Recommended values:**

- Web-UI Network Scan: `max_age=10`. Stale entries vanish within a refresh cycle.
- Long-running router/runner process: do not pass `max_age` on every call — trust the backend's TTL, but call `discover(max_age=60)` periodically as a sweep.

Cross-reference with `cbt.4`: the failover circuit breaker eats stale entries from a different angle — even if a zombie shows up in `discover()`, two consecutive `/v1/health` failures will skip it. Belt and braces.

## Multi-NIC binding

A Saturn server with both Wi-Fi and Ethernet (or any host with multiple routable interfaces) used to advertise on one address only — `get_lan_ip()` returns whichever interface has the default route. Clients on the *other* interface couldn't see the service.

`cbt.6` (§17.G.2) introduces `saturn/mdns/interfaces.py` with `routable_addrs()` — every non-loopback, non-link-local IPv4 address on a UP interface, sourced via `psutil.net_if_addrs()`/`net_if_stats()`.

**Userspace backend** now passes the full address list to `zeroconf.ServiceInfo(addresses=...)`. Bonjour and Avahi already advertised on all interfaces (`interfaceIndex=0` / `AVAHI_IF_UNSPEC`); userspace was the regression.

**Operator knob:**

```
SATURN_ADVERTISE_ALL=1   # default; advertises on all routable interfaces
SATURN_ADVERTISE_ALL=0   # legacy single-IP behavior — only set if you have a reason
```

**Verification:** from a client on each subnet, run Network Scan. The same `node_id` should appear in both — different `host` values, same `id` in TXT.

**Failure modes:** if `psutil` import fails (rare; it's a hard dep), Saturn falls back to single-IP `get_lan_ip()` with a startup warning. If no interface is UP, advertise raises and the server refuses to start.

## AP-isolation probe

"Captive portal" / "client isolation" / "AP isolation" — the access point blocks client-to-client traffic, including multicast. eduroam and most guest Wi-Fi do this. Saturn can advertise into the void and find nothing, with no obvious symptom.

`cbt.5` (§17.G.1) ships `saturn/mdns/isolation.py:probe(timeout=4.0)`. It registers a transient `_saturn-probe._tcp.local.` on a random port, browses for it, and returns:

| Result | Diagnosis |
|---|---|
| `self_seen=True, peers_seen>=1` | Healthy LAN |
| `self_seen=True, peers_seen=0, ifaces_with_link>=1` | **Suspected AP isolation** — your peers exist but the AP is dropping the traffic |
| `self_seen=False, advertising=True, ifaces_with_link>=1` | Loopback multicast broken (firewall, rare) |
| `self_seen=False, ifaces_with_link=0` | No network |

The Web-UI `/api/discover` response carries the probe result on the `isolation` key. When `suspected_ap_isolation=True`, the Network Scan tab replaces the "No peers found" card with a diagnosis + a one-click link to manual configuration. **No auto-fix is possible** — the AP is the problem; Saturn just labels the failure clearly so operators don't waste time chasing the wrong cause.

**Operator action when probe says AP-isolation:** switch to manual config (point each client at a known server `host:port` directly). Or move clients onto a network that doesn't isolate — trying to "fix" multicast on the AP rarely works.

## Large TXT validation

mDNS responses ride UDP. Above ~1500 bytes they fragment, and many switches drop fragmented multicast. Saturn used to silently build oversize TXT records when the model list grew.

`cbt.8` (`173ad9e`, §17.G.4) ships `saturn/mdns/txt.py` with two checks, run at advertise time before delegating to the backend:

1. Per-entry: any `key=value` over 255 bytes raises `TxtTooLarge` (RFC 6763 §6.1 cap).
2. Total: the encoded TXT — `1 + len("k=v")` summed over all entries — over `TXT_SAFE_CEILING` (default 1200 bytes) raises `TxtTooLarge`.

**Order of pruning** (`SaturnAdvertiser.register()`): truncate `models` first, then `capabilities`, then `features`, setting `mtrunc=1` so consumers know the payload is partial. If even minimal pruning can't fit the ceiling, register fails loudly with the offending key sizes — better to refuse to advertise than to ship a record that gets fragmented.

**Operator knob:**

```
SATURN_TXT_CEILING=1200  # default; raise only on jumbo-frame networks (rare)
```

**What to check if `saturn serve` exits with `TxtTooLarge`:** the error includes the byte count. Almost always one of:

- `models` list too long — check your runner config; trim or accept truncation.
- A capability value with a long opaque blob — usually a misconfiguration; capabilities should be short tags.

## Triage

Start here at 2am.

| Symptom | First check |
|---|---|
| "I can't see any peers" | Run `python -c "from saturn.mdns.isolation import probe; print(probe())"` from the affected host. If `suspected_ap_isolation=True`, the AP is dropping multicast. Move to manual config. |
| "I see one peer; my colleague sees a different one" | Multi-NIC issue. Confirm `SATURN_ADVERTISE_ALL=1` (default). Check `routable_addrs()` returns both IPs on the server. |
| "A peer keeps appearing in `rejected[]`" | TOFU rebind. Either the peer's `~/.saturn/node_id` rotated (unexpected — investigate) or you have two peers claiming the same service name (a deploy bug). Don't approve until you know which. |
| "Discovery is slow" | `discover()` is bounded by `settle_time` after the last add (default 1.0s) or `timeout` (8.0s). Lower `settle_time` for the UI; raise `timeout` if you have a known-slow LAN. |
| "Stale peers haunt the cache" | Pass `max_age=` to `discover()`. The backend's TTL is the source of truth, but it can be slow on hard crashes. |
| "saturn serve refuses to start with TxtTooLarge" | Your TXT exceeds the safe ceiling. Trim the offending key (usually `models`) or raise `SATURN_TXT_CEILING` if you actually run on jumbo frames. |

## References

- `saturn/discovery.py` — `discover()`, `SaturnService`, `SaturnAdvertiser`.
- `saturn/mdns/{settle,interfaces,isolation,txt,known_nodes}.py` — the modules called out above.
- `DISCOVERY_AUDIT.md` — geoff's pre-contract audit; deeper detail on settle, parallel resolves, identity churn, cache TTL.
- `PRE_SPECS_B3.md §17.G.{1–4}` — field-level pre-specs for the four mDNS edges.
- `docs/admin/network-troubleshooting.md` — operator triage flowchart for multicast issues.
- `docs/admin/failover.md` — what happens after a peer is found and starts to fail.
