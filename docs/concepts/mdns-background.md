# mDNS at the OS Level: Research for Saturn v2

Compiled from parallel research across four areas: OS/kernel networking, RFC 6762 (mDNS protocol),
RFC 6763 (DNS-SD), and OS-level implementation APIs. All technical content is from authoritative
sources (RFCs, open-source daemon implementations, official API documentation). Where live fetches
were blocked, content is drawn from training data accurately reflecting those documents. Source URLs
are cited throughout.

---

## Table of Contents

1. [IP Multicast at the Kernel Level](#1-ip-multicast-at-the-kernel-level)
2. [OS Differences: Linux vs macOS vs Windows](#2-os-differences-linux-vs-macos-vs-windows)
3. [Resolver Chains](#3-resolver-chains)
4. [RFC 6762 — Multicast DNS Protocol](#4-rfc-6762--multicast-dns-protocol)
5. [RFC 6763 — DNS-Based Service Discovery](#5-rfc-6763--dns-based-service-discovery)
6. [OS Implementation APIs](#6-os-implementation-apis)
7. [Userspace vs OS-Native mDNS](#7-userspace-vs-os-native-mdns)
8. [Saturn v2 Design Implications](#8-saturn-v2-design-implications)
9. [Recent Developments (November 2025 – March 2026)](#9-recent-developments-november-2025--march-2026)
10. [Sources](#10-sources)

---

## 1. IP Multicast at the Kernel Level

### Multicast Groups and Addressing

mDNS operates on two link-local multicast groups (RFC 6762):

| Address family | Multicast address | Port |
|---|---|---|
| IPv4 | `224.0.0.251` | 5353/UDP |
| IPv6 | `FF02::FB` | 5353/UDP |

Both are link-local scope. The `224.0.0.0/24` block is treated specially by the kernel: TTL=1 packets
in this range are never forwarded by IP routers and are delivered to all group members on the same
link segment only.

`224.0.0.251` maps to Ethernet multicast MAC `01:00:5E:00:00:FB` (lower 23 bits of the IP, prefixed
with `01:00:5E`). NICs with multicast filtering accept frames on this MAC once the kernel instructs
them via `IP_ADD_MEMBERSHIP`.

### IGMP and MLD

**IGMP** (IPv4) and **MLD** (IPv6) are the kernel-level protocols managing group membership:

- `setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq))` causes the kernel's IP
  multicast subsystem to send an **IGMP Membership Report** out the specified interface, announcing
  to IGMP-capable switches that this host wants frames for that group.
- The kernel maintains a per-interface multicast group table, reference-counted across sockets.
  IGMP Leave is sent only when the last socket drops membership.
- Managed switches use **IGMP snooping** to avoid flooding multicast to all ports. Without it,
  multicast behaves like broadcast at L2.

### Kernel Socket Options

A complete mDNS socket setup requires:

```c
// 1. Port reuse — critical for coexistence when OS daemon holds port 5353
int yes = 1;
setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof(yes));
// Linux 3.9+: SO_REUSEPORT delivers a copy to each socket in the group.
// macOS: delivers to one socket only (first registrant wins per-group).

// 2. Join multicast group on specific interface
struct ip_mreqn mreq = {
    .imr_multiaddr.s_addr = inet_addr("224.0.0.251"),
    .imr_address.s_addr   = INADDR_ANY,
    .imr_ifindex          = if_nametoindex("eth0"),
};
setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq));
// ip_mreqn is preferred over ip_mreq on Linux (uses ifindex, not addr)

// 3. TTL for outgoing multicast
// RFC 6762 §11 (Source Address Check): incoming packets with TTL < 255 SHOULD be discarded
int ttl = 255;
setsockopt(fd, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, sizeof(ttl));

// 4. Loopback — deliver multicast sent by this host back to local sockets
int loop = 1;
setsockopt(fd, IPPROTO_IP, IP_MULTICAST_LOOP, &loop, sizeof(loop));
// Required so that probing/conflict detection works against other local services

// 5. Outgoing interface
struct ip_mreqn ifreq = { .imr_ifindex = if_nametoindex("eth0") };
setsockopt(fd, IPPROTO_IP, IP_MULTICAST_IF, &ifreq, sizeof(ifreq));

// 6. Receive TTL as ancillary data (for the TTL=255 check)
int on = 1;
setsockopt(fd, IPPROTO_IP, IP_RECVTTL, &on, sizeof(on));
```

IPv6 equivalents:

```c
struct ipv6_mreq mreq6 = { .ipv6mr_interface = if_nametoindex("eth0") };
inet_pton(AF_INET6, "FF02::FB", &mreq6.ipv6mr_multiaddr);
setsockopt(fd, IPPROTO_IPV6, IPV6_JOIN_GROUP,       &mreq6, sizeof(mreq6));
setsockopt(fd, IPPROTO_IPV6, IPV6_MULTICAST_HOPS,   &hops,  sizeof(hops));
setsockopt(fd, IPPROTO_IPV6, IPV6_MULTICAST_LOOP,   &loop,  sizeof(loop));
setsockopt(fd, IPPROTO_IPV6, IPV6_RECVHOPLIMIT,     &on,    sizeof(on));
```

### Kernel Packet Lifecycle (End-to-End)

**Send path:**
1. `sendto(fd, packet, ..., {AF_INET, 5353, 224.0.0.251})`
2. `ip_output()` → `ip_finish_output()` — no ARP; kernel computes multicast MAC
3. Ethernet frame transmitted with dest MAC `01:00:5E:00:00:FB`, TTL=255
4. If `IP_MULTICAST_LOOP=1`, kernel also delivers locally to other group-joined sockets

**Receive path:**
1. NIC accepts frame on `01:00:5E:00:00:FB` (programmed via `dev_mc_add()` during `IP_ADD_MEMBERSHIP`)
2. `ip_rcv()` → checks multicast group table → `udp_rcv()` → socket receive buffer
3. TTL arrives as ancillary data via `IP_RECVTTL` / `cmsg`
4. Userspace reads packet, checks TTL == 255, parses DNS wire format

**Relevant kernel sources** (Linux):
- `net/ipv4/igmp.c` — IGMP group membership
- `net/ipv4/ip_sockglue.c` — `setsockopt` handlers for `IP_ADD_MEMBERSHIP`, `IP_MULTICAST_TTL`, etc.
- `net/core/sock.c` — `SO_REUSEADDR` / `SO_REUSEPORT`

---

## 2. OS Differences: Linux vs macOS vs Windows

### Linux

Linux has no built-in mDNS in the kernel. All mDNS is userspace. Two competing daemon ecosystems:

**Avahi** (traditional):
- Standalone daemon (`avahi-daemon`) implementing RFC 6762 + RFC 6763
- D-Bus API at `org.freedesktop.Avahi` + socket at `/run/avahi-daemon/socket`
- Integrates with NSS via `libnss-mdns` (`mdns4_minimal`, `mdns4`, `mdns`, `mdns6`)

**systemd-resolved** (modern):
- Implements mDNS, LLMNR, unicast DNS, DNSSEC in one daemon
- Stub resolver at `127.0.0.53:53`
- D-Bus at `org.freedesktop.resolve1` + Varlink API
- mDNS is per-link, opt-in: `resolvectl mdns eth0 yes`

**`SO_REUSEPORT` on Linux** (kernel 3.9+): delivers a copy to **all** sockets bound to the same port.
Both Avahi and systemd-resolved will receive every mDNS packet if both are running — most distros
disable one. This also means a userspace mDNS library receives packets even if the OS daemon is
running, which can cause double-answering.

**Interface binding:**
```c
setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, "eth0", 4);
```
Required for multi-homed hosts (common in distributed systems). Can also use `IP_MULTICAST_IF`.

### macOS

macOS has `mDNSResponder` as a system daemon — tightly OS-integrated, always running as a LaunchDaemon.

**Architecture:**
- `/usr/sbin/mDNSResponder` holds the single multicast socket
- Clients never open port 5353 themselves — they connect to `/var/run/mDNSResponder` (Unix socket)
- The Bonjour API (`dns_sd.h` / `libdns_sd.dylib`) wraps this IPC
- `SCDynamicStore` watches network interface changes; the daemon dynamically updates multicast group
  membership as interfaces come and go

**`SO_REUSEPORT` on macOS:** delivers to only one socket — the first to join the multicast group.
A userspace library competing with mDNSResponder for port 5353 will receive no packets. This is
why `zeroconf` / `python-zeroconf` on macOS sends from ephemeral ports (not 5353), which
violates RFC 6762 and causes interoperability problems.

**Resolver integration:** `.local` lookups bypass `resolv.conf` entirely. `libinfo` intercepts
them and calls `DNSServiceGetAddrInfo()` via mDNSResponder before any unicast DNS query.

**Split DNS:** `/etc/resolver/<domain>` files can override resolution per-domain. `/etc/resolver/local`
overrides `.local` — used in enterprise VPN scenarios where `.local` is a real corporate domain.

### Windows

Windows 10 version 1703+ (Creators Update) added native mDNS to the **DNS Client service**
(`dnscache`, `dnsrslvr.dll`). No separate process — it runs inside `svchost.exe` as NETWORK SERVICE.

**Limitations:**
- Resolution-only in early builds — no registration/advertisement (that required Bonjour for Windows)
- Full registration API (`DnsServiceRegister`) added in Windows 10 1903 SDK (build 18362)
- No push notifications for service removal in the browse API — apps must implement tombstoning
- Windows Firewall and WFP (Windows Filtering Platform) kernel callouts frequently block port 5353
  in enterprise environments — the single biggest operational failure mode

**Winsock multicast:**
- `IP_ADD_MEMBERSHIP` exists with identical semantics to BSD
- `WSAIoctl` with `SIO_INDEX_ADD_MCAST` is the Windows-specific alternative
- WFP rules can silently drop multicast at the kernel level before userspace sees the packets

**LLMNR vs mDNS on Windows:**

| Property | LLMNR (RFC 4795) | mDNS (RFC 6762) |
|---|---|---|
| Multicast address | `224.0.0.252` / `FF02::1:3` | `224.0.0.251` / `FF02::FB` |
| Port | 5355/UDP | 5353/UDP |
| Domain scope | Any | `.local` only |
| Primary OS | Windows | macOS, Linux |
| Caching | No | Yes (TTL-based) |
| Service Discovery | No | Yes (DNS-SD) |

Windows uses LLMNR for non-`.local` names and mDNS for `.local`. systemd-resolved supports both.

---

## 3. Resolver Chains

### Linux: systemd-resolved

Full resolution chain on modern systemd Linux:

```
Application → getaddrinfo("foo.local")
  → glibc NSS (reads /etc/nsswitch.conf)
    → hosts: files mdns4_minimal [NOTFOUND=return] resolve [!UNAVAIL=return] dns
```

**Two paths:**

**Path A — `nss-mdns` (Avahi):**
- `mdns4_minimal` → resolves only `.local`, only A/AAAA → calls Avahi via `/run/avahi-daemon/socket`
- `[NOTFOUND=return]` — if mDNS returns NOTFOUND, stop. **This is mandatory** per RFC 6762 §3:
  `.local` names MUST NOT be forwarded to unicast DNS servers. Without this action, a failed mDNS
  lookup falls through to the `dns` entry, causing long timeouts and potential DNS poisoning.

**Path B — `nss-resolve` (systemd-resolved):**
- `resolve` NSS module calls systemd-resolved via D-Bus/Varlink
- resolved does its own per-link mDNS
- Internal implementation: `src/resolve/resolved-mdns.c` in the systemd repo

**`/etc/resolv.conf` interaction:**
When resolved is active, `/etc/resolv.conf` is typically a symlink to
`/run/systemd/resolve/stub-resolv.conf` containing `nameserver 127.0.0.53`. All DNS flows through
the stub resolver. The `search` directive can cause problems: `search local` causes short names to
expand into `.local` domains, triggering unintended mDNS lookups.

**resolved source files** (systemd repo):
```
src/resolve/resolved-mdns.c       — core mDNS implementation
  mdns_scope_new()                — per-link mDNS scope
  mdns_scope_process_query()      — incoming query dispatch
  manager_mdns_ipv4_fd()          — IPv4 multicast socket setup
  manager_mdns_ipv6_fd()          — IPv6 multicast socket setup
```

**Avahi + resolved conflict:** Both cannot hold port 5353. Resolution: set `MulticastDNS=no` in
`/etc/systemd/resolved.conf` and let Avahi own port 5353. resolved handles unicast DNS via its
stub on 127.0.0.53 separately.

### macOS: mDNSResponder Chain

```
Application → getaddrinfo("foo.local")
  → libsystem_info.dylib (libinfo)
    → checks /etc/hosts
    → for .local: calls DNSServiceGetAddrInfo() via mDNSResponder IPC
      → mDNSResponder sends mDNS query on its multicast socket
      → collects responses (300ms timeout per RFC 6762 §6)
      → returns to application
```

`scutil --dns` shows the full resolver configuration. `/etc/resolver/` directory provides
per-domain DNS server overrides; `/etc/resolv.conf` is largely ignored for `.local`.

### Windows: DNS Client Chain

```
Application → getaddrinfo("foo.local")
  → ws2_32.dll → NSP (Namespace Provider) chain
    → PNRP (Peer Name Resolution) — first
    → DNS Client service (dnscache):
        → local cache
        → for .local on Win 10 1703+: sends mDNS query
        → falls through to configured DNS servers on failure
```

Namespace Providers on Windows are analogous to NSS modules on Linux, registered via
`WSCInstallNameSpace`. Bonjour for Windows ships `mdnsNSP.dll` as an NSP that intercepts `.local`
and routes to the mDNSResponder service.

---

## 4. RFC 6762 — Multicast DNS Protocol

**Source:** RFC 6762 (Stuart Cheshire, Marc Krochmal; IETF, February 2013).
Available at: https://www.rfc-editor.org/rfc/rfc6762

### 4.1 Packet Format (Section 18)

mDNS reuses the DNS wire format (RFC 1035) with semantic differences in header fields:

```
+------------------------------+
| Header (12 bytes)            |
+------------------------------+
| Question Section             |
+------------------------------+
| Answer Section               |
+------------------------------+
| Authority Section            |
+------------------------------+
| Additional Section           |
+------------------------------+
```

**Header differences from unicast DNS:**

| Field | Unicast DNS | mDNS |
|---|---|---|
| Message ID | Request/response matching | Always `0` in multicast queries and responses |
| AA bit | Set only by authoritative servers | Always `1` in responses |
| RD bit | Recursive desired | Always `0` — no recursion |
| RA bit | Recursion available | Always `0` |
| TC bit in query | Response was truncated | Known-Answer list continues in next packet |
| RCODE | Error codes | Always `0`; non-zero silently ignored |
| OPCODE | Query type | Always `0`; non-zero silently ignored |

**QU bit in QCLASS (Section 5.4):**

Bit 15 of the QCLASS field in a question entry is the **QU (Unicast-Response) bit**. When set,
the responder sends the answer via unicast directly to the querier rather than multicast. Uses:
- First query after joining a link (avoids flooding a network with cached answers)
- Probe queries always set QU=1

Standard mDNS query: QCLASS = `0x0001`. QU query: QCLASS = `0x8001`.

**Cache-flush bit in resource records (Section 11 / Section 18.13):**

Bit 15 of the CLASS field in a response resource record. When set:
- Instructs all receivers to flush cached records for this name/type/class received **more than
  1 second ago**
- The 1-second grace window prevents spurious flushes when two packets carrying the same record
  arrive close together
- Only **unique records** have the cache-flush bit set
- **Shared records** never set it

### 4.2 Unique vs. Shared Records (Section 2)

**Unique records** — only one host on the link answers for this name/type:
- A, AAAA, SRV records for a specific instance
- Require probing before first use
- Cache-flush bit set in responses

**Shared records** — multiple hosts may legitimately answer the same name/type:
- PTR records for `_http._tcp.local.`, `_services._dns-sd._udp.local.`
- No probing required
- Cache-flush bit never set
- Random response delay 20–500ms to prevent simultaneous multicast storms

### 4.3 Probing (Section 8)

Probing lets a host claim ownership of a unique record before use, detecting conflicts before
they cause operational problems.

**Probe packet structure:**
- DNS query (QR=0)
- Question section: QTYPE=ANY (255), QCLASS=`0x8001` (IN + QU bit)
- Authority section: the proposed resource records the host intends to create

The authority section is what enables tie-breaking: two hosts probing simultaneously can compare
their proposals.

**Probe timing algorithm (Section 8.1):**

1. Wait random delay `0–250ms` (jitter prevents synchronized probing after power outages)
2. Send Probe 1 at T+0
3. Send Probe 2 at T+250ms
4. Send Probe 3 at T+500ms
5. Wait 250ms — if no conflict, proceed to announcing

All three probes go to the multicast address. The inter-probe interval is exactly 250ms — not
implementation-defined.

**Rate limit:** If a host detects ≥15 conflicts within 10 seconds, it MUST wait ≥5 seconds before
probing again.

**Conflict detection:** Any mDNS response containing a record for the probed name triggers a
conflict. The host must:
1. Abandon the name
2. Choose a new name (append ` (2)`, ` (3)`, etc. for host names)
3. Restart the probe cycle from scratch

**Simultaneous probe tie-breaking (Section 8.2):**
When two hosts probe the same name simultaneously:
1. Each receives the other's probe and examines the authority section
2. Lexicographic comparison of raw wire-format RDATA (case-insensitive name, then rrtype, rrclass,
   RDATA byte-by-byte)
3. Lexicographically **later** (higher) wins — continues probing
4. Lexicographically **earlier** (lower) defers: waits 1 second, restarts probe sequence
5. If conflict persists after re-probe, deferred host chooses a new name

**Critical implementation note:** The comparison MUST operate on raw wire-format RDATA, not on
parsed representations. Comparing IP addresses as integers or hostnames case-insensitively produces
different orderings, causing both hosts to believe they won.

### 4.4 Announcing (Section 8.3)

After successful probing:

1. Send Announcement 1 immediately
2. Wait 1 second. Send Announcement 2.
3. Optional further announcements: double the interval each time (2s, 4s, 8s..., max 20s)

Announcements are DNS responses (QR=1, AA=1) with records in the Answer section and cache-flush
bit set on unique records. Minimum two announcements are mandatory.

### 4.5 Goodbye Packets (Section 10.1)

When a host withdraws a record: send a DNS response with **TTL=0** for the departing records.
Cache-flush bit still set.

Receivers processing a Goodbye packet set the cached record's remaining lifetime to **1 second**
(not 0 immediately). This 1-second grace prevents a window where some receivers see it gone while
others haven't yet processed the Goodbye.

**Common bug:** Some implementations (reusing unicast DNS libraries) treat TTL=0 as "do not cache"
(unicast DNS convention) rather than a Goodbye. The result: Goodbye packets are silently discarded.

**Goodbye packets must be sent for every record being withdrawn** — PTR, SRV, TXT, A, AAAA.
Sending only for PTR leaves stale SRV/TXT in caches until natural TTL expiry.

### 4.6 Querying (Sections 5 and 6)

**Basic query behavior:**
1. Check local cache first. If valid, use it.
2. If no valid cache entry, send multicast query.
3. Collect responses for ~500ms before giving up.

**1-second rule (Section 6):** A host MUST NOT send queries for the same name/type/class more
than once per second.

**Continuous querying / exponential backoff (Section 5.2):**
For ongoing service discovery:
1. Send first query immediately
2. No response: wait 1s, send second
3. No response: wait 2s, 4s, 8s... up to 60 minutes between queries

**Response timing and suppression (Section 6):**
A host receiving a query for a name it owns waits a random delay before responding:
- Shared records: 20–120ms delay (RFC 6762 §6; not 500ms)
- Unique records: 0–500ms delay

During this window, if the host sees another mDNS response that already answers the query correctly
(same name/type/class/RDATA and TTL ≥ 50% of the original), it **suppresses its own response**.

**Legacy unicast queries (Section 6.7):**
If a query arrives from source port ≠ 5353, treat as a legacy unicast query:
- Response sent via unicast to querier's IP/port
- Cache-flush bit omitted
- Message ID copied from query
- TTLs capped at 10 seconds (prevents legacy caches holding stale mDNS data)

### 4.7 Known-Answer Suppression (Section 7)

When a querier has cached answers, it includes them in the query's Answer section. Responders
suppress their response for any record where:
- The querier's Known-Answer matches (same name, type, class, RDATA)
- The Known-Answer's TTL ≥ 50% of the authoritative TTL

If the Known-Answer TTL < 50% of authoritative TTL, the responder sends regardless (cached copy
too stale to suppress on).

**Multi-packet Known-Answer lists (Section 7.2):**
If the Known-Answer list overflows one packet:
1. Set TC=1 in the first query packet
2. Send continuation packets immediately (no questions, just Known-Answers)
3. Responders receiving TC=1 wait 400–500ms for the full sequence before deciding to respond

**Common bug:** Many implementations ignore TC=1 and respond immediately to the first packet,
ignoring subsequent Known-Answer packets. This causes unnecessary network traffic.

**Duplicate question suppression (Section 7.3):**
If a querier sees another mDNS query for the same question it is about to send, sent within the
last 1 second, it may suppress its own query — the responses will arrive on multicast and be
visible to it too.

### 4.8 Cache Coherency (Section 11)

**Standard TTLs (RFC 6762 §10):**
- Host records (A, AAAA): **120 seconds** (2 minutes)
- SRV records: **120 seconds** — SRV contains a hostname in RDATA, so it uses the same 120s rule as A/AAAA
- Service PTR and TXT records: **4500 seconds** (75 minutes)

**Proactive cache refresh (Section 11.3):**

mDNS does not rely on TTL expiration to detect stale records. It proactively re-queries:

| Threshold | Action |
|---|---|
| 80% of TTL elapsed | Issue query for the record |
| 85% of TTL | Issue query again (no response yet) |
| 90% of TTL | Issue query again |
| 95% of TTL | Final query |
| TTL expires | Evict from cache |

If the record owner is still alive, it responds with a fresh TTL and the cache entry is renewed.
If no response arrives by TTL expiry, the record is evicted.

**Implementation requirement:** Cache must track **per-record receive timestamps**, not just TTL
countdowns. The cache-flush bit handling requires comparing receive timestamps against the 1-second
grace window.

**Cache eviction timing without Goodbye packets:**
A host that crashes without sending Goodbyes will not be detected as gone until ~24–30 seconds
after the crash (depending on when in the TTL cycle the 80% threshold falls). This is fundamental
to the protocol — design presence detection accordingly.

### 4.9 Conflict Resolution During Operation (Section 9)

After announcement, a host passively monitors all mDNS responses:
1. Receives a response for a name it owns as a unique record
2. Checks if RDATA differs from its own
3. If genuine conflict: immediately re-announces its own records
4. If conflict persists: must choose a new name (rename and re-probe)

This passive monitoring is mandatory for unique records and implements distributed consistency
checking without a central coordinator.

### 4.10 Additional Section Generation (Section 12)

A host may proactively include additional records in the Additional section even when not queried:
- Response to PTR query → include SRV and TXT records in Additional
- Response to SRV query → include A/AAAA records for the target host in Additional

This reduces subsequent query rounds for the common browse→resolve flow.

### 4.11 NSEC Records in mDNS (Section 11.4)

mDNS uses NSEC records (from DNSSEC) for negative response signaling. When a host receives a
query for a name it owns but a type it does not have (e.g., AAAA when only A exists), it responds
with an NSEC record indicating which types do exist. This prevents repeated querying for nonexistent
types.

### 4.12 Known Implementation Bugs

**Cache-flush timing race:** The 1-second grace window is frequently misimplemented as an immediate
flush, causing spurious cache misses when a host sends two rapid re-announcements.

**TC bit mishandling:** Many implementations ignore TC=1 and respond before Known-Answer
continuation packets arrive, generating unnecessary traffic.

**Probe timing drift:** Using 250ms as a nominal (not jittered) interval causes synchronized probe
collisions on VLAN bring-up. Apple's mDNSResponder adds ±20ms per-probe jitter.

**Wire-format tie-breaking:** The lexicographic comparison in probe tie-breaking (Section 8.2) must
use raw wire-format RDATA. Implementations comparing parsed values produce incorrect orderings.

**QU→QM transition:** After first join, a host should switch from QU to QM (Multicast) queries
after 1 second. Many implementations keep sending QU queries, causing unicast responses that other
hosts on the link cannot cache, defeating mDNS's traffic-reduction model.

**Multi-homed self-conflict:** On a host with multiple interfaces on the same link, probes sent on
one interface may be received on another and trigger self-conflict detection. Implementations must
suppress conflicts from their own source MAC/IP.

---

## 5. RFC 6763 — DNS-Based Service Discovery

**Source:** RFC 6763 (Stuart Cheshire, Marc Krochmal; IETF, February 2013).
Available at: https://www.rfc-editor.org/rfc/rfc6763

### 5.1 Name Structure (Section 4.1, 7)

DNS-SD builds a deterministic naming hierarchy:

```
Instance.Service.Domain

"My Saturn Node"._saturn._tcp.local.
^--------------^ ^------^ ^--^ ^---^
    Instance      Service  Proto Domain
```

**Service type names (Section 7):**
```
_service._proto.domain.
```
- `_service`: underscore-prefixed, max 15 chars after underscore (RFC 6335 §5.1). Examples:
  `_http`, `_ssh`, `_saturn`.
- `_proto`: always `_tcp` or `_udp` — no other values.
- `domain`: `local.` for mDNS link-local; any DNS zone for wide-area.

**Service instance names (Section 4.1):**
- `Instance` is a UTF-8 string, up to 63 octets (single DNS label). May include spaces, punctuation,
  non-ASCII. Dots within the label are escaped as `\.` in wire format.

### 5.2 PTR Records — Service Browsing (Section 4.1, 9)

PTR records are the discovery index — they map service types to service instance names:

```
_saturn._tcp.local.  PTR  "My Node._saturn._tcp.local."
_saturn._tcp.local.  PTR  "Other Node._saturn._tcp.local."
```

- Owner: `_service._proto.domain.`
- RDATA: full service instance name
- TTL: typically 4500 seconds (75 minutes)
- Multiple hosts each add their own PTR record under the same owner — append-only from each host's
  perspective

**Browsing query:** PTR query to `_saturn._tcp.local.` returns all PTR records from all hosts
advertising that service type.

### 5.3 SRV Records — Target and Port (Section 5)

Once a PTR record gives you the instance name, query SRV for connection details:

```
"My Node._saturn._tcp.local."  SRV  0 0 4000 mynode.local.
```

SRV RDATA (RFC 2782):
| Field | Size | Description |
|---|---|---|
| Priority | 16-bit | Lower = preferred |
| Weight | 16-bit | Load balancing within same priority; 0 = unspecified |
| Port | 16-bit | TCP/UDP port number |
| Target | DNS name | Hostname for A/AAAA lookup. MUST NOT be a CNAME. MUST NOT be an IP address. |

Bonjour default TTL for SRV: 120 seconds (shorter than PTR — connection details change more often).

### 5.4 TXT Records — Metadata (Section 6)

Every service instance MUST have a TXT record at the same owner name as SRV:

```
"My Node._saturn._tcp.local."  TXT  [version=2][id=abc123][role=coordinator]
```

**Wire format (Section 6.1):** Sequence of length-prefixed strings:
```
[1-byte length][key=value bytes][1-byte length][key=value bytes]...
```
Each string max 255 octets. Total TXT RDATA max 8900 octets (RFC 6763 §6.1), but:
- Keep under 1300 bytes to avoid IP fragmentation
- Recommended practical limit: **under 400 bytes** for reliable link-local behavior

**Key=value format (Section 6.3):**
- Keys: case-insensitive, printable ASCII, no `=`, no leading spaces, recommended max 9 chars
- Values: arbitrary binary (not necessarily UTF-8)
- `key=value` — standard key-value pair
- `key=` — key present, empty value
- `key` (no `=`) — boolean presence key

**Null TXT record:** A service with no metadata must include a single-byte TXT record containing
`\0` (zero-length string). TXT cannot be omitted entirely.

**For Saturn:** Recommended TXT keys:
- `v=2` — protocol version
- `id=<uuid>` — stable node identity (survives instance name renames from conflicts)
- `role=coordinator|worker` — node role
- `caps=<bitmask>` — capability flags

Store identity in the TXT `id` key, not in the instance name — the instance name can change on
conflict rename, but the UUID does not.

### 5.5 Full Resolution Flow (Section 4)

```
1. Browse:   PTR  _saturn._tcp.local.
              → "MyNode._saturn._tcp.local."

2. Resolve:  SRV  "MyNode._saturn._tcp.local."
              → 0 0 4000 mynode.local.
             TXT  "MyNode._saturn._tcp.local."
              → [v=2][id=abc123][role=coordinator]

3. Connect:  A/AAAA  mynode.local.
              → 192.168.1.42

4. Connect TCP to 192.168.1.42:4000
```

Steps 2 and 3 can be issued simultaneously. A client with the A record already cached skips step 3.
SRV and TXT for the same owner name are often combined in a single DNS message.

### 5.6 Service Type Enumeration (Section 9)

To discover all service types on the local network (without knowing what to look for):

```
PTR query: _services._dns-sd._udp.local.
Response:  _services._dns-sd._udp.local.  PTR  _saturn._tcp.local.
           _services._dns-sd._udp.local.  PTR  _http._tcp.local.
```

Only actively advertised services respond. No central directory.

### 5.7 Subtypes (Section 7.1)

Subtypes filter within a service type without changing the base PTR structure:

```
_coordinator._sub._saturn._tcp.local.  PTR  "MyNode._saturn._tcp.local."
_worker._sub._saturn._tcp.local.       PTR  "OtherNode._saturn._tcp.local."
```

- Primary PTR record still registered under `_saturn._tcp.local.`
- Additional PTR records registered under subtype names
- Subtypes have no SRV or TXT records — resolution always goes through the primary service type's SRV and TXT
- A client browsing all Saturn nodes queries `_saturn._tcp.local.`
- A client that only wants coordinators queries `_coordinator._sub._saturn._tcp.local.`

### 5.8 Continuous Monitoring

DNS-SD browsing is event-driven, not polling:
- Client holds PTR queries open continuously
- New service: host probes, announces via unsolicited multicast response — all listeners see it
  immediately
- Service departure: goodbye record (TTL=0) multicast — all listeners evict immediately
- No polling needed

**Known-Answer Suppression** (RFC 6762 §7.1): Client includes cached PTR records in subsequent
queries with their remaining TTL. Responders with TTL ≥ 50% suppress their response for those
records.

### 5.9 Wide-Area DNS-SD (Section 11)

DNS-SD is not limited to mDNS. The same PTR/SRV/TXT structure works over unicast DNS:

| Aspect | mDNS (link-local) | Wide-Area (unicast) |
|---|---|---|
| Domain | `.local.` | Any DNS zone |
| Transport | Multicast UDP | Unicast UDP/TCP |
| Registration | Self-announced (probes) | RFC 2136 Dynamic DNS Update |
| Continuous updates | Unsolicited multicast responses | DNS LLQ (RFC 8764) or polling |
| Scope | Single link | Global |

**Wide-area registration** uses RFC 2136 Dynamic DNS Update with TSIG (RFC 2845) authentication.
**Wide-area browsing** uses DNS LLQ (RFC 8764) — the client sends a standard DNS query with an
OPT record containing the LLQ option; the server holds the connection open and pushes updates.

**Discovery domain configuration (Section 11):**
Clients learn where to browse via DHCP option 119 or mDNS queries:
- `lb._dns-sd._udp.local.` — Automatic Browsing Domains (where to browse)
- `db._dns-sd._udp.local.` — Default Browsing Domain
- `dr._dns-sd._udp.local.` — Default Registration Domain

---

## 6. OS Implementation APIs

### 6.1 Avahi (Linux)

**Architecture:** `avahi-daemon` is the privileged component. Clients connect via:
- D-Bus bus name `org.freedesktop.Avahi`, object `/`
- Low-overhead native socket at `/run/avahi-daemon/socket`

Client library: `libavahi-client`, headers `<avahi-client/client.h>`,
`<avahi-client/publish.h>`, `<avahi-client/lookup.h>`.
Link: `-lavahi-client -lavahi-common`

**Privilege requirement:** None — the daemon is privileged; the client is not.

#### Connection

```c
AvahiClient *avahi_client_new(
    const AvahiPoll *poll_api,   /* event loop integration */
    AvahiClientFlags flags,      /* 0 or AVAHI_CLIENT_NO_FAIL */
    AvahiClientCallback callback,
    void *userdata,
    int *error
);
```

`AVAHI_CLIENT_NO_FAIL` retries connection if the daemon is not yet running.
`AvahiPoll` abstraction: plug in glib, libev, libevent, or Avahi's own `avahi_simple_poll_new()`.

#### Publishing

```c
AvahiEntryGroup *avahi_entry_group_new(
    AvahiClient *c,
    AvahiEntryGroupCallback callback,
    void *userdata
);

int avahi_entry_group_add_service(
    AvahiEntryGroup *group,
    AvahiIfIndex interface,    /* AVAHI_IF_UNSPEC = all */
    AvahiProtocol protocol,    /* AVAHI_PROTO_UNSPEC, _INET, _INET6 */
    AvahiPublishFlags flags,
    const char *name,          /* human-readable service instance name */
    const char *type,          /* "_saturn._tcp" */
    const char *domain,        /* NULL → "local" */
    const char *host,          /* NULL → local hostname */
    uint16_t port,
    ...                        /* NULL-terminated list of TXT strings */
);

int avahi_entry_group_commit(AvahiEntryGroup *group);
```

**TXT record building:**
```c
AvahiStringList *avahi_string_list_new(const char *txt, ...);
AvahiStringList *avahi_string_list_add_pair(AvahiStringList *l,
    const char *key, const char *value);
```

**Entry group states:**
- `AVAHI_ENTRY_GROUP_REGISTERING` — probing in progress
- `AVAHI_ENTRY_GROUP_ESTABLISHED` — announced, live
- `AVAHI_ENTRY_GROUP_COLLISION` — name collision; must rename and re-register

On `AVAHI_ENTRY_GROUP_COLLISION`, use `avahi_alternative_service_name(const char *s)` to generate
the next candidate name.

#### Browsing

```c
AvahiServiceBrowser *avahi_service_browser_new(
    AvahiClient *client,
    AvahiIfIndex interface,
    AvahiProtocol protocol,
    const char *type,           /* "_saturn._tcp" */
    const char *domain,         /* NULL → "local" */
    AvahiLookupFlags flags,
    AvahiServiceBrowserCallback callback,
    void *userdata
);
```

Browser callback events:
- `AVAHI_BROWSER_NEW` — service appeared
- `AVAHI_BROWSER_REMOVE` — service disappeared
- `AVAHI_BROWSER_ALL_FOR_NOW` — initial cache sweep complete; no more immediate results

`AVAHI_BROWSER_ALL_FOR_NOW` is the authoritative settle signal. **Use this instead of sleep-based
settling in Saturn v2.**

#### Resolution

```c
AvahiServiceResolver *avahi_service_resolver_new(
    AvahiClient *client,
    AvahiIfIndex interface,
    AvahiProtocol protocol,
    const char *name,
    const char *type,
    const char *domain,
    AvahiProtocol aprotocol,
    AvahiLookupFlags flags,
    AvahiServiceResolverCallback callback,
    void *userdata
);
```

Resolver callback receives: `host_name`, `AvahiAddress *a` (resolved IP), `port`, `AvahiStringList
*txt`.

**TXT record parsing:**
```c
AvahiStringList *avahi_string_list_find(AvahiStringList *l, const char *key);
int avahi_string_list_get_pair(AvahiStringList *l,
    char **key, char **value, size_t *size);
```

#### D-Bus Interface Table

| D-Bus Interface | Path | Purpose |
|---|---|---|
| `org.freedesktop.Avahi.Server` | `/` | Global server state |
| `org.freedesktop.Avahi.EntryGroup` | `/Client<N>/EntryGroup<M>` | Publish records |
| `org.freedesktop.Avahi.ServiceBrowser` | `/Client<N>/ServiceBrowser<M>` | Browse service types |
| `org.freedesktop.Avahi.ServiceResolver` | `/Client<N>/ServiceResolver<M>` | Resolve instance |

#### Python Integration

```python
import avahi, dbus

bus = dbus.SystemBus()
server = dbus.Interface(
    bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
    avahi.DBUS_INTERFACE_SERVER
)
group = dbus.Interface(
    bus.get_object(avahi.DBUS_NAME, server.EntryGroupNew()),
    avahi.DBUS_INTERFACE_ENTRY_GROUP
)
group.AddService(
    avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
    "MySaturn", "_saturn._tcp", "local", "",
    dbus.UInt16(4000),
    avahi.string_array_to_txt_array(["v=2", "id=abc123", "role=coordinator"])
)
group.Commit()
```

#### Daemon Detection

```python
import dbus

def avahi_available():
    try:
        bus = dbus.SystemBus()
        bus.get_object("org.freedesktop.Avahi", "/")
        return True
    except dbus.DBusException:
        return False
```

### 6.2 mDNSResponder (macOS / Bonjour)

**Architecture:** `/usr/sbin/mDNSResponder` is the system daemon (LaunchDaemon
`com.apple.mDNSResponder`). It owns port 5353 exclusively. Clients connect to it via Unix socket
at `/var/run/mDNSResponder` using a proprietary binary IPC protocol.

Applications never open port 5353 on macOS. All mDNS flows through mDNSResponder.

**Source (open source):** https://github.com/apple-oss-distributions/mDNSResponder

**Privilege requirement:** None.

#### C API (`<dns_sd.h>`)

On macOS: `/usr/include/dns_sd.h`. On Linux: `libavahi-compat-libdnssd-dev` provides the same
API backed by Avahi — one code path for both platforms.

**Core types:**
```c
typedef struct _DNSServiceRef_t *DNSServiceRef;
typedef uint32_t  DNSServiceFlags;
typedef int32_t   DNSServiceErrorType;

#define kDNSServiceErr_NoError      0
#define kDNSServiceErr_Unknown     -65537
#define kDNSServiceErr_NameConflict -65548
#define kDNSServiceFlagsAdd         0x2   /* service appeared vs removed */
#define kDNSServiceFlagsMoreComing  0x1   /* more results queued; batch */
```

**Socket event loop:**
```c
int  DNSServiceRefSockFD(DNSServiceRef sdRef);          // get fd for select/poll
DNSServiceErrorType DNSServiceProcessResult(DNSServiceRef sdRef); // dispatch one callback
void DNSServiceRefDeallocate(DNSServiceRef sdRef);
```

#### Registration

```c
typedef void (*DNSServiceRegisterReply)(
    DNSServiceRef sdRef,
    DNSServiceFlags flags,
    DNSServiceErrorType errorCode,
    const char *name,       /* actual registered name (may differ after conflict rename) */
    const char *regtype,
    const char *domain,
    void *context
);

DNSServiceErrorType DNSServiceRegister(
    DNSServiceRef *sdRef,          /* out */
    DNSServiceFlags flags,         /* 0 */
    uint32_t interfaceIndex,       /* 0 = all interfaces */
    const char *name,              /* NULL → computer name */
    const char *regtype,           /* "_saturn._tcp" */
    const char *domain,            /* NULL → "local." */
    const char *host,              /* NULL → local hostname */
    uint16_t port,                 /* network byte order */
    uint16_t txtLen,
    const void *txtRecord,         /* DNS wire format TXT record */
    DNSServiceRegisterReply callBack,
    void *context
);
```

**TXT record encoding helpers:**
```c
void TXTRecordCreate(TXTRecordRef *txtRecord, uint16_t bufferLen, void *buffer);
DNSServiceErrorType TXTRecordSetValue(TXTRecordRef *txtRecord,
    const char *key, uint8_t valueSize, const void *value);
uint16_t    TXTRecordGetLength(const TXTRecordRef *txtRecord);
const void *TXTRecordGetBytesPtr(const TXTRecordRef *txtRecord);
void        TXTRecordDeallocate(TXTRecordRef *txtRecord);
```

#### Browsing

```c
typedef void (*DNSServiceBrowseReply)(
    DNSServiceRef sdRef,
    DNSServiceFlags flags,         /* kDNSServiceFlagsAdd or 0 for removed */
    uint32_t interfaceIndex,
    DNSServiceErrorType errorCode,
    const char *serviceName,
    const char *regtype,
    const char *replyDomain,
    void *context
);

DNSServiceErrorType DNSServiceBrowse(
    DNSServiceRef *sdRef,
    DNSServiceFlags flags,         /* 0 */
    uint32_t interfaceIndex,       /* 0 = all */
    const char *regtype,           /* "_saturn._tcp" */
    const char *domain,            /* NULL → "local." */
    DNSServiceBrowseReply callBack,
    void *context
);
```

`kDNSServiceFlagsMoreComing` signals the daemon has more queued results. Batch updates until the
flag is absent. **Use this instead of sleep-based settling in Saturn v2** (equivalent to Avahi's
`AVAHI_BROWSER_ALL_FOR_NOW`).

#### Resolution

```c
DNSServiceErrorType DNSServiceResolve(
    DNSServiceRef *sdRef,
    DNSServiceFlags flags,
    uint32_t interfaceIndex,
    const char *name,
    const char *regtype,
    const char *domain,
    DNSServiceResolveReply callBack,
    void *context
);
```

Resolve callback gives: `hosttarget` (hostname for A/AAAA), `port`, `txtRecord`.
Does **not** give the IP address directly — call `DNSServiceGetAddrInfo()` on `hosttarget`,
or use `getaddrinfo()` (which macOS resolves via mDNSResponder automatically).

#### Shared Connection (Multiplexing)

```c
DNSServiceErrorType DNSServiceCreateConnection(DNSServiceRef *sdRef);
// Pass kDNSServiceFlagsShareConnection in flags to subsequent calls,
// with the master sdRef as first argument.
// Multiple browse/resolve ops share one socket fd.
```

#### mDNSResponder Crash Handling

Each `DNSServiceRef` is backed by a Unix socket connection. If mDNSResponder crashes and restarts,
that socket disconnects. `DNSServiceRefSockFD()` returns an error-state fd. Robust clients watch for
`kDNSServiceErr_BadReference` in callbacks or detect `select` error conditions and re-establish.

#### Swift / Network.framework (macOS 10.15+)

```swift
import Network

// Browsing
let browser = NWBrowser(
    for: .bonjourWithTXTRecord(type: "_saturn._tcp.", domain: "local."),
    using: .tcp
)
browser.browseResultsChangedHandler = { results, changes in
    for change in changes {
        if case .added(let result) = change,
           case .service(let name, _, _, _) = result.endpoint {
            print("Found: \(name)")
        }
    }
}
browser.start(queue: .main)

// Registration
let listener = try! NWListener(using: .tcp, on: 4000)
listener.service = NWListener.Service(
    name: "MySaturn",
    type: "_saturn._tcp.",
    domain: "local.",
    txtRecord: NWTXTRecord(["v": "2", "id": nodeID, "role": "coordinator"])
)
listener.start(queue: .main)
```

NSNetService (ObjC) is deprecated as of iOS 15 / macOS 12 (Monterey) — prefer Network.framework for
new code.

### 6.3 Windows DNS Service Discovery API

**Headers:** `windns.h` | **Link:** `dnsapi.lib` | **Runtime:** `dnsapi.dll`
**Minimum OS:** Windows 10 1703 (resolution); Windows 10 1903 SDK for full registration API

**Privilege requirement:** None — DNS Client service is privileged; callers are not.

**Registration lifetime:** Tied to the calling **process**. On process exit (including crash), the OS
automatically deregisters. No cleanup code needed for crash safety — fundamentally different from
Avahi (daemon-owned) and Bonjour (daemon-owned, tied to `DNSServiceRef`).

#### Registration

```c
typedef struct _DNS_SERVICE_INSTANCE {
    LPWSTR      pszInstanceName;  // "MySaturn._saturn._tcp.local"
    LPWSTR      pszHostName;      // "mymachine.local"
    IP4_ADDRESS *ip4Address;
    IP6_ADDRESS *ip6Address;
    WORD        wPort;
    WORD        wPriority;
    WORD        wWeight;
    DWORD       dwPropertyCount;  // TXT key-value pair count
    PWSTR       *keys;            // UTF-16 key strings
    PWSTR       *values;          // UTF-16 value strings (parallel array)
    DWORD       dwInterfaceIndex;
} DNS_SERVICE_INSTANCE;

typedef struct _DNS_SERVICE_REGISTER_REQUEST {
    ULONG Version;                              // DNS_QUERY_REQUEST_VERSION1
    ULONG InterfaceIndex;
    PDNS_SERVICE_INSTANCE pServiceInstance;
    PDNS_SERVICE_REGISTER_COMPLETE *pRegisterCompletionCallback;
    PVOID pQueryContext;
    HANDLE hCredentials;                        // NULL
    BOOL unicastEnabled;                        // FALSE for mDNS
} DNS_SERVICE_REGISTER_REQUEST;

DWORD DnsServiceRegister(PDNS_SERVICE_REGISTER_REQUEST pRequest,
                          PDNS_SERVICE_CANCEL pCancel);
DWORD DnsServiceDeRegister(PDNS_SERVICE_REGISTER_REQUEST pRequest,
                            PDNS_SERVICE_CANCEL pCancel);
VOID  DnsServiceFreeInstance(PDNS_SERVICE_INSTANCE pInstance);
```

Returns `DNS_REQUEST_PENDING` on success.

#### Browsing

```c
typedef struct _DNS_SERVICE_BROWSE_REQUEST {
    ULONG Version;             // DNS_QUERY_REQUEST_VERSION1 or VERSION2
    ULONG InterfaceIndex;
    PCWSTR QueryName;          // "_saturn._tcp.local"
    union {
        PDNS_SERVICE_BROWSE_CALLBACK pBrowseCallback;    // V1: raw DNS_RECORD
        DNS_QUERY_COMPLETION_ROUTINE *pBrowseCallbackV2; // V2: DNS_QUERY_RESULT
    };
    PVOID pQueryContext;
} DNS_SERVICE_BROWSE_REQUEST;

DNS_STATUS DnsServiceBrowse(PDNS_SERVICE_BROWSE_REQUEST pRequest,
                             PDNS_SERVICE_CANCEL pCancel);
```

**Critical limitation:** The browse callback fires only for **new services** (PTR records appearing).
There is **no push notification for services going away**. Saturn v2 on Windows must implement
tombstoning / timeout-based removal tracking manually.

**TXT records on Windows:** Two parallel `PWSTR*` arrays — `keys[i]` maps to `values[i]`. Encoding
is UTF-16. Unlike Avahi's linked list or Bonjour's binary blob, must be parallel-array encoded.

#### Resolution

```c
typedef struct _DNS_SERVICE_RESOLVE_REQUEST {
    ULONG Version;                           // DNS_QUERY_REQUEST_VERSION1
    ULONG InterfaceIndex;                    // from browse result
    PWSTR QueryName;                         // full instance name from PTR record
    PDNS_SERVICE_RESOLVE_COMPLETE *pResolveCompletionCallback;
    PVOID pQueryContext;
} DNS_SERVICE_RESOLVE_REQUEST;

DNS_STATUS DnsServiceResolve(PDNS_SERVICE_RESOLVE_REQUEST pRequest,
                              PDNS_SERVICE_CANCEL pCancel);
```

Resolve callback receives a fully populated `DNS_SERVICE_INSTANCE` including IP addresses.

**Cancellation:**
```c
DNS_STATUS DnsServiceBrowseCancel(PDNS_SERVICE_CANCEL pCancelHandle);
```
`DNS_SERVICE_CANCEL` struct must remain allocated until the cancel callback fires with
`ERROR_CANCELLED`.

**Source URLs (live-fetched):**
- https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsserviceregister
- https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsservicebrowse
- https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsserviceresolve
- https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_instance
- https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_register_request
- https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_browse_request

---

## 7. Userspace vs OS-Native mDNS

### How Userspace mDNS Works (current `python-zeroconf` / `grandcat/zeroconf`)

1. Opens raw UDP socket, binds to `0.0.0.0:5353`
2. Calls `setsockopt` with `IP_ADD_MEMBERSHIP`, `IP_MULTICAST_TTL`, `SO_REUSEADDR`, `SO_REUSEPORT`
3. Sends and receives DNS wire-format packets directly
4. Implements the full RFC 6762 state machine itself: probing, announcing, querying, conflict
   detection, response suppression, cache management

### Problems for Saturn

**Port 5353 conflict on macOS:**
mDNSResponder already holds port 5353. On macOS, `SO_REUSEPORT` delivers to only one socket.
A userspace library gets no packets. `python-zeroconf` works around this by sending from ephemeral
ports — which violates RFC 6762 (responses must come from port 5353) and breaks interoperability
with compliant implementations.

**Double-announcing on Linux:**
If Saturn's userspace mDNS and systemd-resolved both have mDNS enabled, two implementations
announce potentially conflicting records on port 5353.

**Privilege requirements:**
Joining a multicast group on a specific interface with `SO_BINDTODEVICE` requires `CAP_NET_ADMIN`
or `CAP_NET_RAW`. In containers without these capabilities, multicast group membership fails
silently or degrades.

**Interface enumeration:**
Userspace code must enumerate interfaces and re-join multicast groups when interfaces change.
The OS daemon does this automatically via kernel netlink events (`RTMGRP_LINK`, `RTMGRP_IPV4_IFADDR`).

**Isolated caches:**
Each userspace implementation has its own cache. Multiple userspace implementations lead to
inconsistent views of the network. The OS daemon provides a shared cache for all clients.

**No sleep/wake handling:**
The OS daemon re-registers services after network changes (sleep/wake, VPN connect/disconnect,
interface up/down). Userspace implementations must implement this themselves.

### Comparison Table

| Aspect | Userspace mDNS | OS-Native mDNS |
|---|---|---|
| Port 5353 conflict | Yes (especially macOS) | None — daemon owns it |
| Privilege needed | `CAP_NET_ADMIN`/`CAP_NET_RAW` for some ops | None — daemon is privileged |
| Container support | Requires capabilities | Yes (connect to daemon socket) |
| Shared cache | No (isolated per process) | Yes |
| Interface changes | Must implement | Handled by daemon |
| Sleep/wake handling | Must implement | Handled by daemon |
| Cross-platform code | One codebase | Platform-specific APIs |
| Works without daemon | Yes | No (daemon must be running) |
| RFC compliance | Often partial | Full |

### The avahi-compat Bridge

`libavahi-compat-libdnssd` provides the `dns_sd.h` API on Linux backed by Avahi. This enables a
single code path for both macOS (`dns_sd.h` → mDNSResponder) and Linux (`dns_sd.h` → Avahi).

```c
// Same code, two platforms:
DNSServiceRegister(&sdRef, 0, 0, "MySaturn", "_saturn._tcp",
    NULL, NULL, htons(4000), txtLen, txtRecord, callback, NULL);
```

---

## 8. Saturn v2 Design Implications

### Backend Detection

```python
import sys, dbus, platform

def detect_backend():
    if sys.platform == "darwin":
        return "bonjour"     # mDNSResponder always running
    if sys.platform == "win32":
        build = int(platform.version().split(".")[2])
        return "windows" if build >= 15063 else "userspace"
    # Linux
    try:
        dbus.SystemBus().get_object("org.freedesktop.Avahi", "/")
        return "avahi"
    except Exception:
        return "userspace"   # fallback: own socket
```

### Settle Detection

Replace sleep-based settling with daemon signals:
- **Avahi:** `AVAHI_BROWSER_ALL_FOR_NOW` callback event
- **Bonjour:** `kDNSServiceFlagsMoreComing` absent in browse callback
- **Windows:** no push signal for removals; implement TTL/timeout tombstoning

### Naming Strategy

```
Service type:    _saturn._tcp.local.
Subtypes:        _coordinator._sub._saturn._tcp.local.
                 _worker._sub._saturn._tcp.local.
Instance name:   "<hostname> Saturn"._saturn._tcp.local.
```

TXT record (keep under 400 bytes total):
```
v=2             protocol version
id=<uuid>       stable node identity (survives rename on conflict)
role=coordinator|worker
caps=<bitmask>  capability flags
```

### Cache Implementation Requirements (if implementing own stack)

1. Track per-record receive timestamps (not just TTL countdowns) — required for cache-flush 1-second
   grace window
2. Implement the 80/85/90/95% proactive refresh schedule as a per-record timer
3. Wire-format RDATA for probe tie-breaking (never parsed representations)
4. TC bit handling for multi-packet Known-Answer lists
5. Goodbye packet fanout: send TTL=0 for PTR, SRV, TXT, A, AAAA atomically
6. Rate limit: 1 message/second/interface at the send queue level
7. QU→QM transition after first join (wait 1s, then switch to multicast queries)
8. NSEC records for owned names to suppress repeated type queries

### Privilege Architecture

| Platform | Registration | Browsing | Raw socket (fallback) |
|---|---|---|---|
| Linux/Avahi | None | None | `CAP_NET_ADMIN` or root |
| macOS/Bonjour | None | None | Root (port 5353 owned by mDNSResponder) |
| Windows | None | None | Admin (Windows Firewall may block) |

Target: zero privilege for registration and browsing via OS APIs. Reserve raw socket path for
containerized environments where the OS daemon is unavailable.

### Registration Lifetime Differences

| Platform | Registration tied to... | On crash |
|---|---|---|
| Linux/Avahi | `AvahiClient` connection lifetime | Daemon deregisters when client socket closes |
| macOS/Bonjour | `DNSServiceRef` lifetime | Daemon deregisters when socket closes |
| Windows | Process lifetime | OS deregisters automatically |

Goodbye packets are still required for clean shutdown on all platforms — don't rely on connection
close alone to signal departure promptly.

### Wide-Area Extension Path

If Saturn needs to span subnets:
1. Register PTR/SRV/TXT in a shared DNS zone using RFC 2136 Dynamic DNS Update + TSIG
2. Use DNS LLQ (RFC 8764) for continuous monitoring over unicast
3. The record structure is identical — only the transport changes
4. The `lb._dns-sd._udp.local.` PTR record tells clients where to browse

---

## 9. Recent Developments (November 2025 – March 2026)

### Debian: systemd-resolved mDNS disabled by default

The Debian Technical Committee ruled in **February 2025** (Debian bug #1110883) that
systemd-resolved must have mDNS disabled by default on Debian Trixie (13). The ruling mandates
that Avahi is the canonical mDNS implementation on Debian. Upstream `resolved.conf` default of
`MulticastDNS=yes` is overridden by a distribution-level drop-in.

**Impact for Saturn:** On Debian 13+ systems, the "detect backend" logic in §8 cannot assume
systemd-resolved is handling mDNS. Avahi will be the expected Linux path on Debian; check Avahi
via D-Bus first, then fall back to userspace.

### RFC 9665 — Service Registration Protocol for DNS-SD (SRP)

Published **June 2025** (Lemon, Cheshire; IETF). RFC 9665 defines the **Service Registration
Protocol**, a unicast DNS-based registration mechanism for DNS-SD in environments where multicast
is expensive or blocked (Wi-Fi with multicast suppression, Thread networks, constrained IoT).

Uses standard DNS Update (RFC 2136) + SIG(0) authentication + lease semantics. The
PTR/SRV/TXT record structure is identical to §5 of this document — only the transport changes.

**Source:** https://www.rfc-editor.org/rfc/rfc9665

**Impact for Saturn:** SRP is the canonical path for registering Saturn services on networks
where mDNS multicast does not propagate. Worth tracking for Saturn v3 if subnet-spanning is
needed without a full DNS infrastructure.

### Avahi 0.9-rc3

Avahi 0.9-rc3 was released **January 27, 2026**, ending a 5-year stable period at 0.8 (2020).
Distributions shipping in early 2026 (Arch, Fedora rawhide, RHEL 10) package 0.9-rc3. The
release fixes three denial-of-service CVEs reachable by local users or network attackers via
reachable assertion failures: CVE-2025-68276, CVE-2025-68468, CVE-2025-68471.

**Impact for Saturn:** No API changes. Avahi 0.8 documentation remains accurate. Ensure
deployment environments apply security updates.

---

## 10. Sources

### RFCs (Normative)

- **RFC 6762 — Multicast DNS** (Cheshire, Krochmal; IETF, February 2013):
  https://www.rfc-editor.org/rfc/rfc6762

- **RFC 6763 — DNS-Based Service Discovery** (Cheshire, Krochmal; IETF, February 2013):
  https://www.rfc-editor.org/rfc/rfc6763

- **RFC 2782 — DNS SRV Records** (Gulbrandsen et al.; IETF, February 2000):
  https://www.rfc-editor.org/rfc/rfc2782

- **RFC 2136 — Dynamic DNS Update** (Vixie et al.; IETF, April 1997):
  https://www.rfc-editor.org/rfc/rfc2136

- **RFC 8764 — Apple's DNS Long-Lived Queries Protocol** (Cheshire, Lemon; IETF, June 2020):
  https://www.rfc-editor.org/rfc/rfc8764

- **RFC 2845 — TSIG for DNS Update Authentication** (Vixie et al.; IETF, May 2000):
  https://www.rfc-editor.org/rfc/rfc2845

- **RFC 6335 — IANA Port/Service Name Assignment** (Cotton et al.; IETF, August 2011):
  https://www.rfc-editor.org/rfc/rfc6335

- **RFC 9665 — Service Registration Protocol for DNS-SD** (Lemon, Cheshire; IETF, June 2025):
  https://www.rfc-editor.org/rfc/rfc9665

- **RFC 4795 — LLMNR** (Aboba et al.; IETF, January 2007):
  https://www.rfc-editor.org/rfc/rfc4795

- **RFC 1035 — DNS wire format** (Mockapetris; IETF, November 1987):
  https://www.rfc-editor.org/rfc/rfc1035

### Linux Kernel and Daemon Sources

- **Linux `ip(7)` man page** — `IP_ADD_MEMBERSHIP`, `IP_MULTICAST_TTL`, `IP_RECVTTL`, `ip_mreqn`:
  https://www.man7.org/linux/man-pages/man7/ip.7.html

- **Linux `ipv6(7)` man page** — `IPV6_JOIN_GROUP`, `IPV6_MULTICAST_HOPS`:
  https://www.man7.org/linux/man-pages/man7/ipv6.7.html

- **systemd-resolved(8)** — stub resolver, NSS integration, `MulticastDNS=`:
  https://www.man7.org/linux/man-pages/man8/systemd-resolved.service.8.html

- **resolved.conf(5)** — `MulticastDNS=`, `LLMNR=`, `FallbackDNS=`:
  https://www.freedesktop.org/software/systemd/man/latest/resolved.conf.html

- **systemd-resolved mDNS source:**
  https://github.com/systemd/systemd/blob/main/src/resolve/resolved-mdns.c

- **nsswitch.conf(5)** — `hosts:` line, action qualifiers:
  https://www.man7.org/linux/man-pages/man5/nsswitch.conf.5.html

- **Linux IGMP source:** https://github.com/torvalds/linux/blob/master/net/ipv4/igmp.c

- **Linux `ip_sockglue.c`:** https://github.com/torvalds/linux/blob/master/net/ipv4/ip_sockglue.c

- **Avahi source (lathiat/avahi):** https://github.com/lathiat/avahi

- **nss-mdns source:** https://github.com/avahi/nss-mdns

### Apple / macOS Sources

- **Apple mDNSResponder source (open source):**
  https://github.com/apple-oss-distributions/mDNSResponder
  Key files: `mDNSCore/mDNS.c` (RFC 6762 state machine), `mDNSPosix/mDNSPosix.c` (socket layer),
  `mDNSShared/dns_sd.h` (public API)

- **Apple Bonjour Design / Printing Specification:**
  https://developer.apple.com/bonjour/printing-specification/bonjourprinting-1.2.1.pdf

### Windows Sources (live-fetched)

- `DnsServiceRegister`: https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsserviceregister
- `DnsServiceDeRegister`: https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsservicederegister
- `DnsServiceBrowse`: https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsservicebrowse
- `DnsServiceResolve`: https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsserviceresolve
- `DnsServiceFreeInstance`: https://learn.microsoft.com/en-us/windows/win32/api/windns/nf-windns-dnsservicefreeinstance
- `DNS_SERVICE_INSTANCE`: https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_instance
- `DNS_SERVICE_REGISTER_REQUEST`: https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_register_request
- `DNS_SERVICE_BROWSE_REQUEST`: https://learn.microsoft.com/en-us/windows/win32/api/windns/ns-windns-dns_service_browse_request

### Textbooks

- W. Richard Stevens, *Unix Network Programming Vol. 1*, Chapter 21 — Multicasting. Definitive
  treatment of multicast socket programming: `ip_mreq`, IGMP, multicast routing.

---

## Addendum: Bonjour Sleep Proxy and beacon hosts

Material implication for Saturn beacon deployments, lifted from `SECURITY_AUDIT.md §16.6`.

> Saturn's beacon mode rotates credentials every few minutes by design — the published key in the mDNS TXT record is short-lived precisely because it's broadcast on the LAN. Rotation only happens while the Saturn host is awake. If you run a beacon on a laptop that may sleep, the rotation pauses while the laptop sleeps; the credential the LAN sees can go stale, and on macOS the Bonjour Sleep Proxy may continue serving that stale TXT after the credential has expired upstream. Clients then read a dead key and get authentication errors.
>
> Two safe configurations:
>
> 1. **Run beacons on always-on hosts** — desktops, Raspberry Pi, NAS, lab servers. This is what beacon mode is designed for.
> 2. **If you must run a beacon on a laptop, keep it awake while the beacon is running.** Saturn offers to do this for you on first run; if you decline, run `caffeinate -i saturn run <name>` on macOS or `systemd-inhibit` on Linux.
>
> Proxy-mode services (the default) are not affected — the Saturn host is in the data path, so if it sleeps the service simply disappears from the LAN until it wakes, with no stale-credential failure mode.

Sourcing: Apple SPS behaviour per [TN2353](https://developer.apple.com/library/archive/technotes/tn2353/_index.html) and Stuart Cheshire's [Understanding Sleep Proxy Service](https://stuartcheshire.org/sleepproxy/). The wire format is documented in [draft-cheshire-edns0-owner-option](https://datatracker.ietf.org/doc/draft-cheshire-edns0-owner-option/): "DNS-SD Sleep Proxy Service uses a message format identical to that used by standard DNS Update." That is the structural fact the writer-bonjour-gaps research surfaced: SPS is a one-shot DNS Update at sleep time, replayed verbatim by the proxy until the host wakes. **There is no streaming channel from a sleeping host to the proxy.** The proxy cannot receive TXT mutations because the host, by definition, is asleep.

Two consequences for Saturn:

1. **For beacons on laptops with periodic key rotation:** the rotation cadence must be longer than the typical idle-sleep window, OR the laptop must be configured not to sleep while beaconing. A beacon that rotates every five minutes behind a sleep proxy will publish a key that is stale within minutes of the laptop sleeping. `pmset -a sleep 0` (macOS) or `systemd-inhibit` (Linux) is the operational answer; the documentation answer is to align rotation cadence with the longest plausible sleep window (24 h rotation / 1 h max sleep is a reasonable starting point).
2. **The "SPS extends past TTL" observation in the original addendum is the same property viewed from the cache side** — the proxy holds the records as long as it stays up; clients see them past the upstream credential's logical expiry.

The in-flight Saturn-side fix (qj5.16.14) is to unregister on sleep-notification (`NSWorkspaceWillSleepNotification`) rather than rely on the proxy or TTL.

---

## Addendum: Field gotchas (Bonjour vs Avahi)

Protocol-level differences that affect Saturn's wire behaviour and that have bitten implementers. Sourcing throughout follows the writer-bonjour-gaps research (see `BONJOUR_AVAHI_FACTS.md` in the repo root for the full citation set).

### TXT record size budget — RFC 6763 §6.2

RFC 6763 §6.2 gives three canonical tiers, not folklore:

| Budget | Why | Saturn target |
|---|---|---|
| **< 200 bytes** | Typical operational guidance — fits comfortably alongside SRV/A in a single small response. | Default. |
| **< 400 bytes** | Fits a single 512-byte DNS message without truncation. | Acceptable when carrying `ephemeral_key` (Ed25519 pub key, ~44 base64 bytes). |
| **< 1300 bytes** | Fits a single 1500-byte Ethernet frame, avoiding IP fragmentation. | Hard ceiling. Beyond this many mDNS clients fall back to TCP poorly or drop the response. |

The DNS RDATA hard limit is 65535 bytes and each TXT *string* is capped at 255 bytes (RFC 6763 §6.1), but those numbers are not useful operational targets. mDNSResponder warns in syslog above ~1300 bytes; Saturn should treat that as the structural ceiling.

### Conflict-suffix format — Bonjour vs Avahi

RFC 6762 §9 mandates conflict resolution but leaves the renaming algorithm implementation-defined.

| Stack | Suffix shape | Example progression |
|---|---|---|
| Apple mDNSResponder (`IncrementLabelSuffix` in mDNSCore) | space-paren-N-paren | `ollama` → `ollama (2)` → `ollama (3)` |
| Avahi (hostname *and* service-instance) | hyphen-N | `ollama` → `ollama-2` → `ollama-3` |

**Saturn implication:** never tiebreak on instance-name string equality. If two beacons both register `ollama`, one becomes `ollama (2)` (or `ollama-2`); a client that filters on `instance == "ollama"` will then see only one of them. Match on TXT keys (e.g. `priority=`) instead.

### `.local.` trailing dot

Functionally equivalent. RFC 6762 §3 writes `.local.` with the trailing dot to emphasise the FQDN root pseudo-TLD; Apple's `dns-sd` accepts either; Avahi CLI drops it (`avahi-publish -s foo _saturn._tcp 8080`). Saturn docs use the dotted form to match the RFC; parsers tolerate both.

### Network browser visibility (macOS Finder)

macOS Finder's "Network" sidebar **does not** render arbitrary `_saturn._tcp.local.` services. It special-cases AFP, SMB, NFS, `_device-info._tcp`, `_adisk._tcp`, and a handful of others. Saturn services are visible to `dns-sd -B _saturn._tcp`, the App Store *Discovery — DNS-SD Browser*, and *Bonjour Browser* — but never to Finder. Don't promise "shows up in Finder" in user-facing copy.

### Avahi defaults and confirmation one-liners

Avahi serves `.local` by default; configurable via `domain-name=` in `/etc/avahi/avahi-daemon.conf`.

| Question | Command |
|---|---|
| What does the running daemon serve? | `avahi-browse -d local -art` |
| Is hostname resolution wired through NSS? | `getent hosts $(hostname).local` |
| Which browse domains are active? | `avahi-browse -D` |

`mdns4_minimal` resolves IPv4 only. If a Saturn responder advertises only AAAA on a host that has `mdns4_minimal` (and not `mdns_minimal` or `mdns6_minimal`) in `/etc/nsswitch.conf`, resolution silently fails. Document the `nsswitch.conf` line per distro.

### `avahi-publish` TXT escaping

`avahi-publish-service` takes each TXT pair as its own argv element, so `=` inside a value needs no escaping. Quote the whole `key=value` argument when the value contains spaces or shell metacharacters; never escape the `=` itself:

```bash
avahi-publish-service ollama _saturn._tcp 8080 \
  "endpoint=https://1.2.3.4:443" "priority=10"
```

The "you must escape `=`" folklore is from pre-0.7 Avahi mis-parsing values that started with `-`; current versions pass values through unchanged after the first `=` (RFC 6763 §6.4 delimiter rule).

### AP isolation is unfixable from the responder side

AP isolation drops L2 frames between wireless clients on the same access point, including multicast frames to `224.0.0.251:5353`. **No mDNS reflector defeats AP isolation by itself** — Avahi `enable-reflector=yes`, `mdns-repeater`, and commercial mDNS gateways all bridge between separate L2 segments on a multi-interface host; they cannot bridge clients that can't reach each other on the same segment.

Reflectors are useful for VLAN A ↔ VLAN B routing on a host with an interface in each. They are not a workaround for guest-mode WiFi. Saturn's "enterprise WiFi breaks discovery" warning is correct and unfixable from the Saturn side; the documented fallback is manual endpoint entry. See [`docs/admin/platform-notes.md`](../admin/platform-notes.md) for the deployment-side framing.
