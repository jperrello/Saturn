# Saturn v2 mDNS Gap Analysis

**Intent:** Analyze Saturn against `docs/mdns-os-research.md` across four specific questions:
1. Where does Saturn use userspace zeroconf replaceable with native OS APIs?
2. What RFC compliance gaps exist in Saturn's current mDNS implementation?
3. What security vulnerabilities does Saturn face from recent Avahi CVEs?
4. How could Saturn leverage RFC 9665 (Service Registration Protocol)?

**Sources consulted:** `saturn/discovery.py`, `saturn/runner.py`, `saturn-router/src/mdns.rs`,
`saturn-router/Cargo.toml`, `owui_saturn.py`, `saturn/tests/test_discovery.py`,
`docs/mdns-os-research.md`

---

## Q1 — Userspace Zeroconf Replaceable with Native OS APIs

Saturn uses python-zeroconf (userspace) in five places and mdns-sd (Rust userspace) in one:

### Python layer

| File | Usage | API |
|---|---|---|
| `saturn/discovery.py:12` | `SaturnDiscovery` — browse `_saturn._tcp.local.` | `Zeroconf()`, `ServiceBrowser` |
| `saturn/discovery.py:86` | `SaturnAdvertiser` — register service | `Zeroconf()`, `ServiceInfo`, `register_service()` |
| `owui_saturn.py:10,84-97` | Full browse loop with own `Zeroconf()` instance | `Zeroconf()`, `ServiceBrowser` |
| `vlc_extension/vlc_discovery_bridge.py` | Browse loop for VLC | `Zeroconf()`, `ServiceBrowser` |
| `saturn-mcp/saturn_mcp/server.py:9` | Calls `discover()` from `saturn.discovery` | Inherits python-zeroconf |

`owui_saturn.py` and `vlc_discovery_bridge.py` each construct their own `Zeroconf()` instances,
independent of `SaturnDiscovery`. On macOS this means three or more separate userspace sockets
contending with mDNSResponder on port 5353.

### Rust layer

`saturn-router/src/mdns.rs:2` uses `mdns_sd::{ServiceDaemon, ServiceInfo}` (crate version `0.11`,
per `Cargo.toml`). `mdns-sd` is a pure-Rust userspace mDNS stack — it opens its own UDP socket on
port 5353 and implements the full mDNS protocol internally. On macOS this conflicts with
mDNSResponder. On Linux it conflicts with both Avahi and systemd-resolved if mDNS is enabled in
those daemons.

### What the research doc says is replaceable

Per `docs/mdns-os-research.md` §7 and §8:

**macOS:** Replace `Zeroconf()` + `ServiceBrowser`/`ServiceInfo` calls with the `dns_sd.h` API
(Bonjour / mDNSResponder). On macOS, mDNSResponder always runs and already owns port 5353.
Relevant functions: `DNSServiceRegister`, `DNSServiceBrowse`, `DNSServiceResolve`.
No port conflict, no privilege needed, full RFC compliance delegated to the OS daemon.

**Linux:** Replace `Zeroconf()` with either:
- D-Bus Avahi API (`org.freedesktop.Avahi`) — preferred; no privilege needed
- `libavahi-compat-libdnssd` — drops in as a `dns_sd.h`-compatible shim backed by Avahi

The research doc §8 includes a `detect_backend()` Python snippet that shows the detection logic:
check for Avahi via D-Bus first, fall back to userspace. Saturn has no equivalent detection —
it unconditionally constructs `Zeroconf()` on all platforms.

**Highest-value replacement targets:**
1. `SaturnDiscovery` + `SaturnAdvertiser` in `discovery.py` — core objects, single change cascades
2. `MdnsService` in `saturn-router/src/mdns.rs` — Rust equivalent; on macOS replace with
   `dns-sd` Rust bindings or shell out to `dns-sd` CLI; on Linux call Avahi D-Bus

**Lower-priority targets:**
- `owui_saturn.py` — OWUI integration bridge; duplicates discovery logic that should call into
  `saturn.discovery` anyway rather than constructing its own `Zeroconf()`
- `vlc_extension/vlc_discovery_bridge.py` — narrow VLC use case; can use `saturn discover` CLI
  via subprocess rather than importing zeroconf directly

---

## Q2 — RFC 6762 / 6763 Compliance Gaps

### Gap 1: Sleep-based settling instead of daemon signals

`saturn/discovery.py:186-212` — The `discover()` function uses a `settle_time` heuristic:
poll every 0.25s, exit when no new services have arrived for `settle_time` seconds (default 1.0s).

**RFC issue:** This is inherently racy. A service that responds slowly (e.g., on a congested
network) is dropped. The research doc §8 specifies daemon-level signals as the correct approach:
- Avahi: `AVAHI_BROWSER_ALL_FOR_NOW` callback event
- Bonjour: absence of `kDNSServiceFlagsMoreComing` in browse callback
- Windows: TTL/timeout tombstoning

This gap is directly visible in `saturn/tests/test_discovery.py` which uses `time.sleep(2.5)` and
`time.sleep(3)` throughout — the test suite itself encodes the fragility of timing-based settling.

### Gap 2: No subtype support

`SaturnDiscovery.SERVICE_TYPE = "_saturn._tcp.local."` (discovery.py:80)
`SaturnAdvertiser.SERVICE_TYPE = "_saturn._tcp.local."` (discovery.py:80/348)

Per RFC 6763 §7.1, service subtypes allow filtered browsing without enumerating all instances.
The research doc §8 proposes:
```
_coordinator._sub._saturn._tcp.local.
_worker._sub._saturn._tcp.local.
```
Saturn currently has no concept of node roles (coordinator/worker) at the mDNS layer. All services
broadcast the same type. Clients cannot subscribe to only coordinators without fetching all records
and filtering locally via TXT properties.

### Gap 3: TXT record schema doesn't match research doc recommendation

`SaturnAdvertiser._properties()` (discovery.py:403-438) uses:
```
version = '1.0'
deployment = ...
api_type = ...
```

The research doc §8 recommends:
```
v=2         (protocol version, short key)
id=<uuid>   (stable node identity, survives rename on conflict)
role=coordinator|worker
caps=<bitmask>
```

Saturn's TXT record uses long key names (`version`, `deployment`, `api_type`, `api_base`,
`priority`, `ephemeral_key`, `features`, `models`, `capabilities`, `context`, `cost`) — easily
10+ keys. RFC 6763 §6.4 recommends keeping TXT records under 200 bytes for efficient wire
transport. The research doc says keep total under 400 bytes. Saturn limits the `models` value
to 255 bytes per key (discovery.py:406) but does not enforce a total TXT record budget.

There is also no stable `id` field. If a service is renamed due to conflict resolution, its
identity changes. The research doc notes that a stable UUID (`id=`) survives rename.

### Gap 4: No TTL=255 source address check

RFC 6762 §11: "Multicast DNS implementations SHOULD silently discard any Multicast DNS responses
with IP TTL less than 255." Python-zeroconf does not consistently enforce this. The mdns-sd Rust
crate (version 0.11) also does not expose TTL checking to the application. Saturn has no
application-level guard.

This means Saturn will accept mDNS responses sent from off-link (TTL ≤ 254), enabling spoofing
of service records from outside the local network segment (where routing is present).

### Gap 5: Priority collision avoidance is application-level, not RFC-compliant

`SaturnAdvertiser._find_available_priority()` (discovery.py:383-400) scans the network,
collects priorities, and increments if there's a conflict. This is Saturn-specific application
logic implemented on top of mDNS, not part of RFC 6762 conflict resolution.

RFC 6762 §8 defines conflict resolution via probing (comparing wire-format RDATA). Saturn ignores
this — two Saturns with the same name could both successfully register with slightly different TXT
records, depending on timing. The `_find_available_priority()` scan can return before all services
have announced, leaving a race window.

### Gap 6: Goodbye packet reliability not guaranteed

`SaturnAdvertiser.unregister()` (discovery.py:469-475) calls `self._zeroconf.unregister_service()`.
Python-zeroconf sends TTL=0 goodbye packets but does not guarantee delivery (UDP, no retry).

The research doc §8.3 (Cache Implementation Requirements) item 5 says:
"Goodbye packet fanout: send TTL=0 for PTR, SRV, TXT, A, AAAA atomically"

Python-zeroconf does not do atomic multi-record goodbye. The mdns-sd Rust crate (MdnsService.unregister)
also does a best-effort single unregister call. Stale records persist in peer caches until TTL
expiry (default 4500s per RFC 6762) if goodbye packets are dropped.

---

## Q3 — Avahi CVE Exposure

### CVEs in scope

From `docs/mdns-os-research.md` §9:
- **CVE-2025-68276** — Avahi 0.8, DoS via reachable assertion, network-reachable
- **CVE-2025-68468** — Avahi 0.8, DoS via reachable assertion, network-reachable
- **CVE-2025-68471** — Avahi 0.8, DoS via reachable assertion, local-user-reachable

All three are fixed in Avahi 0.9-rc3 (released January 27, 2026).

### Saturn's current exposure

Saturn's Python components use **python-zeroconf**, not Avahi. The three CVEs do not apply
directly to Saturn's own code.

The Rust component uses **mdns-sd 0.11**, also not Avahi.

**However, indirect exposure exists in three scenarios:**

**Scenario A — Co-deployed Avahi on Linux hosts.**
On Linux, Avahi typically runs as a system daemon alongside Saturn. If Avahi 0.8 is running on the
same host, the three CVEs can be exploited via the network (CVE-2025-68276, CVE-2025-68468) or
by any local user (CVE-2025-68471). Crashing Avahi does not directly crash Saturn's python-zeroconf
stack, but it does:
- Remove the shared mDNS cache, causing other processes relying on Avahi to lose service records
- Silence the mDNS stack for other consumers on the host until Avahi restarts
- On Debian 13+ (where Avahi is the canonical mDNS implementation per the Feb 2025 ruling),
  this disrupts all mDNS on the system

**Scenario B — Saturn deployed in environments where native API integration is added.**
If Saturn is refactored to use Avahi D-Bus (as Q1 recommends), the host Avahi version matters
directly. A crashed Avahi daemon would make `org.freedesktop.Avahi` D-Bus calls fail, requiring
Saturn to handle daemon restart gracefully.

**Scenario C — Credential exposure via mDNS TXT records (Beacon mode).**
`BeaconAdvertiser._properties()` (runner.py:142-156) broadcasts an `ephemeral_key` field in the
mDNS TXT record. This credential is visible to any process on the local network that can receive
mDNS multicast. The CVEs are DoS, not disclosure — but the broader point from the research doc
is that userspace mDNS implementations (python-zeroconf, mdns-sd) have no authentication or
encryption layer. A network attacker on the same L2 segment can read beacon credentials.

The `runner.py:147` check `if len(credential) > 240` only warns — it doesn't truncate or refuse.
Credentials exceeding 240 bytes exceed safe per-key TXT record size and may be split or truncated
by compliant implementations.

### Recommended action from research doc

"No API changes. Avahi 0.8 documentation remains accurate. Ensure deployment environments apply
security updates." — `docs/mdns-os-research.md` §9

Concretely for Saturn: add Avahi version detection to the deployment documentation and the
`detect_backend()` logic proposed in Q1. Refuse to use Avahi D-Bus integration if the detected
version is < 0.9 on platforms where the CVEs are unpatched.

---

## Q4 — RFC 9665 (Service Registration Protocol) Applicability

### What SRP is

RFC 9665 (Lemon, Cheshire; published June 2025) defines the **Service Registration Protocol**:
unicast DNS-SD registration for environments where mDNS multicast is blocked or expensive.
Transport: DNS Update (RFC 2136) + SIG(0) authentication + lease semantics.
Record format: identical PTR/SRV/TXT structure as RFC 6763 — only the transport changes.

### Saturn's current multicast assumption

Saturn assumes mDNS multicast works:
- `SaturnDiscovery` opens `_saturn._tcp.local.` and relies on UDP multicast to port 5353
- `SaturnAdvertiser` sends multicast announcements on registration
- `MdnsService` (Rust) does the same via `mdns_sd::ServiceDaemon`

There is no fallback for environments where multicast is suppressed. No configuration option.
No `SRP_SERVER` environment variable or discovery of SRP server records.

### Environments where Saturn's current model fails

Per `docs/mdns-os-research.md` §9 (SRP section) and §1 (IGMP/multicast kernel section):

1. **Enterprise Wi-Fi with client isolation** — APs with IGMP snooping or client isolation
   enabled drop multicast between stations. Saturn services on different Wi-Fi clients cannot
   discover each other even on the same SSID.
2. **Containerized deployments** — Joining multicast groups requires `CAP_NET_ADMIN` or
   `CAP_NET_RAW`. Containers without these capabilities degrade silently (per research doc §7).
   Saturn has no detection for this failure mode.
3. **Thread/IoT networks** — Out of scope for current Saturn, but relevant if Saturn-adjacent
   services run on embedded nodes.

### How Saturn could leverage RFC 9665

**Registration path:** Saturn services would register PTR/SRV/TXT records via DNS Update (RFC 2136)
to an SRP server rather than multicast. The SRP server is discoverable via:
- `_srp-tls._tcp.local.` PTR record (for secure SRP)
- `_srp._udp.local.` PTR record (for plain SRP)
- Or configured statically via environment variable (`SATURN_SRP_SERVER=<host>:<port>`)

**Discovery path:** Clients query the SRP server directly via unicast DNS rather than joining
`224.0.0.251`. The `discover()` function in `discovery.py` would need a unicast DNS-SD resolver
path alongside the existing `ServiceBrowser` (multicast) path.

**Scope for Saturn v2 vs v3:**
The research doc notes this is "worth tracking for Saturn v3 if subnet-spanning is needed without
a full DNS infrastructure." For Saturn v2, the practical blocker is that SRP servers are not
commonly available on home/office LAN routers (Apple routers support it; most others don't).

A pragmatic v2 approach for multicast-suppressed environments (short of full SRP) is the
DNS LLQ path described in the research doc §8 (Wide-Area Extension):
- Register PTR/SRV/TXT in a shared DNS zone via RFC 2136 + TSIG
- Use DNS LLQ (RFC 8764) for continuous monitoring
This requires a conventional DNS server (BIND, CoreDNS) that Saturn operators control,
which is more deployable than SRP in enterprise contexts today.

---

## Summary of Findings

| Area | Severity | Key Finding |
|---|---|---|
| Userspace zeroconf | High | 5 separate `Zeroconf()` instances across Python files; Rust uses mdns-sd 0.11; no platform detection |
| RFC compliance — settling | Medium | Sleep-based `settle_time` heuristic instead of `AVAHI_BROWSER_ALL_FOR_NOW` / `kDNSServiceFlagsMoreComing` |
| RFC compliance — subtypes | Medium | No subtype support; clients cannot browse by role without fetching all records |
| RFC compliance — TXT schema | Low-Medium | Long key names; no total-budget enforcement; no stable `id=` field |
| RFC compliance — TTL=255 check | Medium | No source-address TTL check; enables off-link spoofing |
| RFC compliance — goodbye packets | Low | Best-effort only; stale records persist up to 4500s |
| Avahi CVEs | Low (indirect) | Saturn doesn't use Avahi directly; risk is to co-deployed Avahi daemons and future D-Bus integration |
| RFC 9665 / SRP | Informational | No support; Saturn fails silently in multicast-suppressed environments; SRP is v3 scope |
