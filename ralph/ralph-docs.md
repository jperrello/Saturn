# Saturn v2 mDNS Subsystem

## Overview

Saturn discovers and advertises AI inference endpoints using multicast DNS
(mDNS / Bonjour / Zeroconf). This lets Saturn nodes find each other on a
LAN with zero configuration — no IP addresses, no service registries.

Service type: `_saturn._tcp`

---

## Backend Selection

`saturn/mdns/detect.py` selects the backend at runtime:

| Platform | Condition | Backend |
|----------|-----------|---------|
| macOS | always | `BonjourBackend` (libdns_sd via ctypes) |
| Linux | Avahi daemon reachable | `AvahiBackend` (D-Bus) |
| Linux | no Avahi | `UserspaceBackend` (zeroconf) |
| Windows | build ≥ 17763 | `WindowsBackend` |
| Windows (old) | — | `UserspaceBackend` |

All backends implement `saturn.mdns.backend.MdnsBackend`:

```python
def advertise(spec: AdvertiseSpec) -> None
def withdraw() -> None
def browse(callback) -> None
def stop_browse() -> None
def close() -> None
```

---

## BonjourBackend (macOS)

`saturn/mdns/bonjour.py` — ctypes bindings to `/usr/lib/libSystem.B.dylib`.

Key functions used:
- `DNSServiceRegister` — registers a service with mDNSResponder
- `DNSServiceBrowse` — browses for `_saturn._tcp` services
- `DNSServiceResolve` — resolves a browsed service to host/port/TXT
- `DNSServiceRefSockFD` + `DNSServiceProcessResult` — event loop via select()
- `DNSServiceRefDeallocate` — releases a ref (sends goodbye packets)

**Crash recovery**: if `kDNSServiceErr_BadReference` (-65563) is returned by
`DNSServiceProcessResult`, the backend re-registers automatically.

**Name conflict**: if `kDNSServiceErr_NameConflict` (-65548) is returned in
the register callback, the conflict handler appends " (2)", " (3)", etc. and
re-registers.

---

## AvahiBackend (Linux)

`saturn/mdns/avahi.py` — D-Bus calls to `org.freedesktop.Avahi`.

Requires Avahi ≥ 0.9-rc3 (CVE-2025-68276/68468/68471 fixes).
Falls back to `UserspaceBackend` if the Avahi daemon is not running.

---

## UserspaceBackend (fallback)

`saturn/mdns/userspace.py` — pure Python using the `zeroconf` library
(requires `zeroconf>=0.131.0,<1.0.0`).

**Limitation on macOS**: responses are sent from ephemeral ports, not 5353.
This violates RFC 6762 §11 and may be ignored by compliant implementations.
Use `BonjourBackend` on macOS instead.

---

## Conflict Handling

`saturn/mdns/conflict.py` — manages the persisted instance name.

If another Saturn node on the same LAN already uses "My Saturn", this node
registers as "My Saturn (2)", then "My Saturn (3)", etc. The chosen name is
persisted in `~/.saturn/instance_name` so it survives restarts.

---

## TXT Record Schema (v2)

Total size target: < 400 bytes.

| Key | Short | Value | Notes |
|-----|-------|-------|-------|
| `id` | — | UUID | Node identity (stable across restarts) |
| `v` | — | `2` | Schema version |
| `version` | — | `1.0` | Service version |
| `dep` | ← new | `network`/`cloud`/`local` | Short alias for `deployment` |
| `deployment` | — | same | Kept for backward compat (1 release) |
| `api_type` | — | `openai` | API dialect |
| `api_base` | — | URL | Endpoint base |
| `priority` | — | integer | Lower = preferred |
| `features` | — | comma-list | e.g. `network_proxy` |
| `models` | — | comma-list | Truncated to 200 bytes |
| `mtrunc` | — | `1` | Present if models list was truncated |
| `capabilities` | — | comma-list | e.g. `chat,vision` |
| `context` | — | integer | Context window size |
| `cost` | — | `free`/`paid`/`unknown` | |
| `ephemeral_key` | — | JWT/token | Beacon only |

Model names are sanitized before insertion: `=`, null bytes, and newlines
are stripped; values are capped at 63 bytes (UTF-8).

---

## Testing

### macOS

```bash
# Advertise a test service and verify mDNSResponder sees it
python3 -c "
from saturn.mdns.bonjour import BonjourBackend
from saturn.mdns.backend import AdvertiseSpec
import time
b = BonjourBackend()
b.advertise(AdvertiseSpec('Saturn-Test', 9999, {'id': 'test', 'v': '2'}))
time.sleep(10)
b.close()
" &
dns-sd -B _saturn._tcp local.
```

### Linux (with Avahi)

```bash
avahi-daemon --check
python3 -c "
from saturn.mdns.avahi import AvahiBackend
from saturn.mdns.backend import AdvertiseSpec
import time
b = AvahiBackend()
b.advertise(AdvertiseSpec('Saturn-Test', 9999, {'id': 'test', 'v': '2'}))
time.sleep(10)
b.close()
" &
avahi-browse -r _saturn._tcp
```

### Unit tests

```bash
python3 -m pytest saturn/tests/ -q
# 101 tests, ~55 seconds (includes mDNS integration tests)
```

Slow tests use real mDNS — they require either mDNSResponder (macOS) or
Avahi/zeroconf on the test host. Mark with `-m "not slow"` to skip them.
