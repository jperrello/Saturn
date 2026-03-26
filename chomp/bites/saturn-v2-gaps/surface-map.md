# Surface Map — Saturn v2 mDNS Gaps

Maps Saturn's current mDNS surface to native OS APIs and RFC requirements.

---

## Userspace → Native OS API

```
saturn/discovery.py:Zeroconf()                 ->  macOS: mDNSResponder via dns_sd.h (DNSServiceRegister/Browse/Resolve)
                                                    Linux: Avahi D-Bus (org.freedesktop.Avahi) or libavahi-compat-libdnssd
                                                    action: replaces

saturn/discovery.py:ServiceBrowser             ->  macOS: DNSServiceBrowse callback
                                                    Linux: avahi_service_browser_new()
                                                    action: replaces

saturn/discovery.py:ServiceInfo + register_service  ->  macOS: DNSServiceRegister
                                                         Linux: avahi_entry_group_add_service()
                                                         action: replaces

owui_saturn.py:Zeroconf()                      ->  Should delegate to saturn.discovery.SaturnDiscovery
                                                    action: replaces (consolidation, not new API)

vlc_extension/vlc_discovery_bridge.py:Zeroconf() ->  Should call `saturn discover --json` via subprocess
                                                       or delegate to saturn.discovery
                                                       action: replaces (consolidation)

saturn-router/src/mdns.rs:ServiceDaemon        ->  macOS: dns-sd Rust bindings or dns-sd CLI subprocess
                                                    Linux: avahi-client-sys crate or Avahi D-Bus via zbus
                                                    action: replaces
```

---

## RFC Compliance Gaps

```
saturn/discovery.py:discover() settle_time loop    ->  AVAHI_BROWSER_ALL_FOR_NOW (Linux/Avahi)
                                                        kDNSServiceFlagsMoreComing absent (macOS/Bonjour)
                                                        action: replaces

SaturnDiscovery.SERVICE_TYPE="_saturn._tcp.local." ->  No equivalent for subtypes
                                                        Missing: _coordinator._sub._saturn._tcp.local.
                                                        Missing: _worker._sub._saturn._tcp.local.
                                                        action: augments

SaturnAdvertiser._properties() TXT schema          ->  research doc §8 recommends: v=, id=, role=, caps=
                                                        Current: version, deployment, api_type, api_base,
                                                                 priority, features, models, capabilities,
                                                                 context, cost, ephemeral_key
                                                        action: replaces (schema alignment)

SaturnAdvertiser._properties() no total-size check ->  RFC 6763 §6.4: keep under 200 bytes preferred, 400 max
                                                        Current: only per-key models truncation at 255 bytes
                                                        action: augments

No TTL=255 check anywhere in saturn/discovery.py   ->  RFC 6762 §11: discard packets with TTL < 255
                                                        action: no equivalent (missing)

SaturnAdvertiser._find_available_priority()        ->  RFC 6762 §8 conflict resolution via probing
                                                        Current: application-level priority scan (racy)
                                                        action: replaces (if using native APIs, daemon handles)

SaturnAdvertiser.unregister()                      ->  RFC 6762 goodbye = TTL=0 for PTR+SRV+TXT+A+AAAA atomic
                                                        Current: python-zeroconf best-effort, not atomic
                                                        action: augments (native APIs handle atomically)

SaturnService.name (no id field)                   ->  RFC 6763 / research doc: stable id= UUID in TXT
                                                        action: no equivalent (missing)
```

---

## Avahi CVE / Security

```
BeaconAdvertiser._properties()['ephemeral_key']   ->  CVE-2025-68276/68468/68471: not directly applicable
                                                        (Saturn uses python-zeroconf, not Avahi)
                                                        Indirect: Avahi 0.8 on same host is vulnerable to DoS
                                                        Security note: ephemeral_key is L2-visible to all
                                                        network participants — no transport encryption
                                                        action: no equivalent (design constraint)

runner.py:147 credential length warning            ->  RFC 6763 §6.1: each TXT key=value ≤ 255 bytes
                                                        Current: warns but does not truncate
                                                        action: augments

No Avahi version detection in detect_backend()     ->  Should refuse Avahi D-Bus integration if Avahi < 0.9
                                                        (research doc §9 recommendation)
                                                        action: no equivalent (missing)
```

---

## RFC 9665 (SRP) Gaps

```
saturn/discovery.py:SaturnDiscovery             ->  RFC 9665 SRP client (DNS Update + SIG(0) + lease)
                                                     action: no equivalent (missing)

saturn/discovery.py:discover()                  ->  Unicast DNS-SD resolver path alongside ServiceBrowser
                                                     action: no equivalent (missing)

SaturnAdvertiser.register()                     ->  SRP registration to _srp-tls._tcp.local. or
                                                     static SATURN_SRP_SERVER config
                                                     action: no equivalent (missing)

No multicast-failure detection                  ->  CAP_NET_ADMIN check, graceful degradation to SRP/unicast
                                                     action: no equivalent (missing)
```

---

## Priority / Effort Summary

```
HIGH IMPACT — Replace with native OS APIs:
  Zeroconf() in discovery.py          ->  dns_sd.h / Avahi D-Bus
  ServiceDaemon in mdns.rs            ->  dns-sd bindings / Avahi D-Bus via zbus

MEDIUM IMPACT — RFC compliance:
  discover() settle_time heuristic    ->  AVAHI_BROWSER_ALL_FOR_NOW / kDNSServiceFlagsMoreComing
  No subtype support                  ->  add _coordinator._sub, _worker._sub types
  No TTL=255 check                    ->  filter on recvmsg ancillary data

LOW IMPACT — Schema / hardening:
  TXT schema alignment                ->  v=, id=, role=, caps= keys
  Total TXT budget enforcement        ->  400-byte total check in _properties()
  Credential length enforcement       ->  truncate/refuse, don't just warn
  Avahi version detection             ->  check before using D-Bus integration

INFORMATIONAL — Future:
  RFC 9665 SRP support                ->  Saturn v3 scope per research doc
  Multicast-failure graceful degradation ->  container/enterprise-Wi-Fi resilience
```
