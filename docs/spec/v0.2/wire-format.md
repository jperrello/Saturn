# Saturn v2 mDNS Technical Specification

**Date:** 2026-03-25
**Status:** Draft
**Scope:** mDNS/DNS-SD subsystem redesign
**Based on:** `docs/mdns-os-research.md`, bite analysis in `chomp/bites/mdns-rfc-gap-analysis/`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture: Multi-Backend mDNS Layer](#2-architecture-multi-backend-mdns-layer)
3. [Backend 1: Avahi (Linux)](#3-backend-1-avahi-linux)
4. [Backend 2: Bonjour / mDNSResponder (macOS)](#4-backend-2-bonjour--mdnsresponder-macos)
5. [Backend 3: Windows DNS-SD API](#5-backend-3-windows-dns-sd-api)
6. [Backend 4: Userspace Fallback](#6-backend-4-userspace-fallback)
7. [TXT Record Schema v2](#7-txt-record-schema-v2)
8. [DNS-SD Subtype Registration](#8-dns-sd-subtype-registration)
9. [Conflict Resolution and Stable Identity](#9-conflict-resolution-and-stable-identity)
10. [Settle Detection](#10-settle-detection)
11. [Migration Path](#11-migration-path)
12. [Performance Targets](#12-performance-targets)
13. [Security Hardening](#13-security-hardening)

---

## 1. Problem Statement

Saturn's current mDNS layer has three concrete failure modes:

**Failure 1: Silent non-compliance on macOS.**
`mDNSResponder` holds port 5353 exclusively. python-zeroconf's workaround sends mDNS
responses from ephemeral source ports. RFC 6762 §11 requires source port 5353. Compliant
implementations discard or deprioritize these responses. Every Saturn developer on a Mac
runs a non-compliant stack without any visible error. Discovery appears to work (same-process
loopback works fine) but cross-host discovery on macOS is degraded.

**Failure 2: Identity lost on name conflict.**
Saturn's instance name is its only identity (`myservice-8080._saturn._tcp.local.`). RFC §8
probing (handled by python-zeroconf) will rename conflicting services to `myservice-8080 (2)`,
etc. Saturn has no conflict callback, no stable UUID, and no rename-and-re-probe cycle.
Any code that tracks services by name breaks silently after a conflict rename.

**Failure 3: Startup race condition in discovery.**
`discover()` uses `time_since_last >= settle_time` (default 1.0s). This is a heuristic with
no protocol basis. On congested or asymmetric networks it either returns too early (missing
peers) or waits longer than necessary (slow startup). The tests encode this fragility as
`time.sleep(2.5)` walls.

---

## 2. Architecture: Multi-Backend mDNS Layer

### 2.1 Abstract Interface

Define a `MdnsBackend` protocol in Python that all backends implement:

```python
# saturn/mdns/backend.py
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, runtime_checkable

@dataclass
class ServiceRecord:
    name: str           # instance name, may change on conflict
    node_id: str        # stable UUID from id= TXT key
    host: str           # resolved IP address
    port: int
    txt: dict[str, str]

@dataclass
class AdvertiseSpec:
    name: str
    port: int
    txt: dict[str, str]  # must include id=<uuid>
    subtypes: list[str] = field(default_factory=list)

ServiceEvent = tuple[str, ServiceRecord]  # ("added"|"removed"|"updated", record)

@runtime_checkable
class MdnsBackend(Protocol):
    def advertise(self, spec: AdvertiseSpec) -> None: ...
    def withdraw(self) -> None: ...
    def browse(self, callback: Callable[[ServiceEvent], None]) -> None: ...
    def stop_browse(self) -> None: ...
    def close(self) -> None: ...
```

### 2.2 Backend Selection

```python
# saturn/mdns/detect.py
import sys
import platform

def select_backend() -> str:
    if sys.platform == "darwin":
        return "bonjour"
    if sys.platform == "win32":
        build = int(platform.version().split(".")[-1])
        return "windows" if build >= 17763 else "userspace"  # Win10 1809+ for stable DNS-SD
    # Linux
    try:
        import dbus
        dbus.SystemBus().get_object("org.freedesktop.Avahi", "/")
        return "avahi"
    except Exception:
        pass
    return "userspace"

def make_backend(name: str | None = None) -> MdnsBackend:
    backend = name or select_backend()
    if backend == "bonjour":
        from saturn.mdns.bonjour import BonjourBackend
        return BonjourBackend()
    if backend == "avahi":
        from saturn.mdns.avahi import AvahiBackend
        return AvahiBackend()
    if backend == "windows":
        from saturn.mdns.windows import WindowsBackend
        return WindowsBackend()
    from saturn.mdns.userspace import UserspaceBackend
    return UserspaceBackend()
```

---

## 3. Backend 1: Avahi (Linux)

### 3.1 Dependencies

```toml
# pyproject.toml extras
[project.optional-dependencies]
avahi = ["dbus-python>=1.3.0"]
```

At runtime, `avahi-daemon` must be running. Detect via D-Bus:
```
org.freedesktop.Avahi at /
```

### 3.2 Registration

```python
# saturn/mdns/avahi.py
import avahi
import dbus
import dbus.mainloop.glib
from gi.repository import GLib

class AvahiBackend:
    SERVICE_TYPE = "_saturn._tcp"

    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()
        self._server = dbus.Interface(
            self._bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
            avahi.DBUS_INTERFACE_SERVER
        )
        self._group: dbus.Interface | None = None
        self._loop = GLib.MainLoop()
        import threading
        threading.Thread(target=self._loop.run, daemon=True).start()

    def advertise(self, spec: AdvertiseSpec) -> None:
        if self._group:
            self._group.Reset()
        else:
            path = self._server.EntryGroupNew()
            self._group = dbus.Interface(
                self._bus.get_object(avahi.DBUS_NAME, path),
                avahi.DBUS_INTERFACE_ENTRY_GROUP
            )
            self._group.connect_to_signal("StateChanged", self._on_group_state)

        txt = avahi.string_array_to_txt_array(
            [f"{k}={v}" for k, v in spec.txt.items()]
        )
        self._group.AddService(
            avahi.IF_UNSPEC,
            avahi.PROTO_UNSPEC,
            dbus.UInt32(0),
            spec.name,
            self.SERVICE_TYPE,
            "local",
            "",                   # use local hostname
            dbus.UInt16(spec.port),
            txt
        )
        # Register DNS-SD subtypes
        for subtype in spec.subtypes:
            self._group.AddServiceSubtype(
                avahi.IF_UNSPEC, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                spec.name, self.SERVICE_TYPE, "local",
                f"{subtype}._sub.{self.SERVICE_TYPE}"
            )
        self._group.Commit()

    def _on_group_state(self, state, error):
        import avahi
        if state == avahi.ENTRY_GROUP_COLLISION:
            # RFC §8: name collision — choose alternative and re-probe
            self._handle_collision()
        elif state == avahi.ENTRY_GROUP_FAILURE:
            raise RuntimeError(f"Avahi registration failed: {error}")

    def _handle_collision(self):
        if self._current_spec is None:
            return
        new_name = self._server.GetAlternativeServiceName(self._current_spec.name)
        from .conflict import update_instance_name
        update_instance_name(new_name)      # persists new name, notifies caller
        self._current_spec.name = new_name
        self.advertise(self._current_spec)  # re-probe with new name

    def withdraw(self) -> None:
        if self._group:
            self._group.Reset()     # sends goodbye packets for all records

    def browse(self, callback):
        self._browser = self._server.ServiceBrowserNew(
            avahi.IF_UNSPEC, avahi.PROTO_UNSPEC,
            self.SERVICE_TYPE, "local", dbus.UInt32(0)
        )
        browser_iface = dbus.Interface(
            self._bus.get_object(avahi.DBUS_NAME, self._browser),
            avahi.DBUS_INTERFACE_SERVICE_BROWSER
        )
        browser_iface.connect_to_signal("ItemNew", lambda *a: self._on_new(callback, *a))
        browser_iface.connect_to_signal("ItemRemove", lambda *a: self._on_remove(callback, *a))
        # AllForNow fires when initial cache sweep is complete
        browser_iface.connect_to_signal("AllForNow", self._on_all_for_now)

    def _on_all_for_now(self):
        self._settle_event.set()    # unblocks discover() immediately
```

**Key property**: `avahi_entry_group_reset()` sends goodbye packets for all records in the
group atomically, including PTR, SRV, TXT, A. No partial goodbye window.

### 3.3 Privilege Model

Avahi registration requires no elevated privileges. The daemon (`avahi-daemon`) is the
privileged component. The D-Bus connection works from any process, including containers
that have access to the system D-Bus socket (`/run/dbus/system_bus_socket`).

### 3.4 Debian 13+ Consideration

On Debian Trixie (13+), systemd-resolved's mDNS is disabled by default and Avahi is
canonical. Detection via D-Bus handles this correctly — if `org.freedesktop.Avahi` is on
the bus, use Avahi; otherwise fall back to userspace.

---

## 4. Backend 2: Bonjour / mDNSResponder (macOS)

### 4.1 Strategy

macOS's `mDNSResponder` holds port 5353 exclusively. The only correct approach is to
delegate all mDNS operations to it via the `dns_sd.h` API or the Python `pybonjour` binding.

```
pip install pybonjour  # wraps libdns_sd.dylib
```

Alternatively, use `ctypes` to call `libdns_sd.dylib` directly — zero new dependencies.

### 4.2 Registration via ctypes

```python
# saturn/mdns/bonjour.py
import ctypes, ctypes.util, socket, threading, struct

_lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("dns_sd"))

DNSServiceRef = ctypes.c_void_p
DNSServiceFlags = ctypes.c_uint32
DNSServiceErrorType = ctypes.c_int32

class BonjourBackend:
    SERVICE_TYPE = "_saturn._tcp"

    def __init__(self):
        self._sd_ref: ctypes.c_void_p | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

    def advertise(self, spec: AdvertiseSpec) -> None:
        if self._sd_ref:
            _lib.DNSServiceRefDeallocate(self._sd_ref)

        # Build TXT record in DNS wire format
        txt_bytes = b""
        for k, v in spec.txt.items():
            entry = f"{k}={v}".encode()
            txt_bytes += bytes([len(entry)]) + entry

        sd_ref = DNSServiceRef()
        err = _lib.DNSServiceRegister(
            ctypes.byref(sd_ref),
            ctypes.c_uint32(0),         # flags
            ctypes.c_uint32(0),         # all interfaces
            spec.name.encode(),
            f"{self.SERVICE_TYPE}.".encode(),
            None,                        # domain: "local."
            None,                        # host: local hostname
            socket.htons(spec.port),
            ctypes.c_uint16(len(txt_bytes)),
            ctypes.c_char_p(txt_bytes),
            self._register_reply,
            None
        )
        if err != 0:
            raise RuntimeError(f"DNSServiceRegister failed: {err}")
        self._sd_ref = sd_ref
        self._start_event_loop()

    @staticmethod
    def _register_reply(sd_ref, flags, err, name, regtype, domain, ctx):
        # name may differ from requested name after conflict rename
        # (kDNSServiceFlagsAdd will be set; err = kDNSServiceErr_NameConflict on failure)
        if err == -65548:  # kDNSServiceErr_NameConflict
            from .conflict import handle_conflict
            handle_conflict()
        elif err != 0:
            import logging
            logging.getLogger("saturn.mdns.bonjour").error(
                f"Registration error {err}"
            )

    def _start_event_loop(self):
        import select
        if self._thread and self._thread.is_alive():
            return
        self._running.set()

        def loop():
            fd = _lib.DNSServiceRefSockFD(self._sd_ref)
            while self._running.is_set():
                r, _, _ = select.select([fd], [], [], 0.5)
                if r:
                    _lib.DNSServiceProcessResult(self._sd_ref)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def withdraw(self) -> None:
        if self._sd_ref:
            # mDNSResponder sends goodbyes on dealloc
            _lib.DNSServiceRefDeallocate(self._sd_ref)
            self._sd_ref = None

    def browse(self, callback):
        # DNSServiceBrowse + DNSServiceResolve on ItemNew
        # kDNSServiceFlagsMoreComing absence = settle signal
        ...
```

**Key property**: `DNSServiceRefDeallocate` instructs mDNSResponder to send goodbye
packets via the daemon's port 5353 socket. No RFC violation. Works in App Sandbox.

### 4.3 Conflict Handling on macOS

The `_register_reply` callback receives the **actual** registered name (may differ from
requested if mDNSResponder renamed it due to a conflict). If `err == kDNSServiceErr_NameConflict`
(-65548), the registration was rejected outright; call the conflict handler to choose a new
name and re-register.

### 4.4 Crash Recovery

If `mDNSResponder` crashes (rare but possible), `DNSServiceRefSockFD` returns an
error-state fd and `DNSServiceProcessResult` returns `kDNSServiceErr_BadReference`.
The event loop must detect this and re-establish the `DNSServiceRef`:

```python
result = _lib.DNSServiceProcessResult(self._sd_ref)
if result == -65563:  # kDNSServiceErr_BadReference
    self._sd_ref = None
    self.advertise(self._current_spec)  # reconnect to restarted daemon
```

---

## 5. Backend 3: Windows DNS-SD API

### 5.1 Requirements

- Windows 10 1903 (build 18362) SDK for full registration
- `windns.h` / `dnsapi.dll`

### 5.2 ctypes Implementation Sketch

```python
# saturn/mdns/windows.py
import ctypes, ctypes.wintypes

_dnsapi = ctypes.windll.LoadLibrary("dnsapi.dll")

class DNS_SERVICE_INSTANCE(ctypes.Structure):
    _fields_ = [
        ("pszInstanceName", ctypes.c_wchar_p),
        ("pszHostName",     ctypes.c_wchar_p),
        ("ip4Address",      ctypes.c_void_p),
        ("ip6Address",      ctypes.c_void_p),
        ("wPort",           ctypes.c_uint16),
        ("wPriority",       ctypes.c_uint16),
        ("wWeight",         ctypes.c_uint16),
        ("dwPropertyCount", ctypes.c_uint32),
        ("keys",            ctypes.c_void_p),   # PWSTR* array
        ("values",          ctypes.c_void_p),   # PWSTR* array
        ("dwInterfaceIndex",ctypes.c_uint32),
    ]

class WindowsBackend:
    SERVICE_TYPE = "_saturn._tcp.local"

    def advertise(self, spec: AdvertiseSpec) -> None:
        keys = (ctypes.c_wchar_p * len(spec.txt))(*spec.txt.keys())
        vals = (ctypes.c_wchar_p * len(spec.txt))(*spec.txt.values())
        inst = DNS_SERVICE_INSTANCE(
            pszInstanceName = f"{spec.name}.{self.SERVICE_TYPE}",
            pszHostName     = None,
            wPort           = spec.port,
            dwPropertyCount = len(spec.txt),
            keys            = ctypes.cast(keys, ctypes.c_void_p),
            values          = ctypes.cast(vals, ctypes.c_void_p),
        )
        # DNS_SERVICE_REGISTER_REQUEST struct + DnsServiceRegister() call
        ...

    def withdraw(self) -> None:
        # DnsServiceDeRegister — process exit also auto-deregisters (Windows guarantee)
        ...
```

**Key Windows caveat**: The browse callback fires only for services *appearing* — there
is no push notification for service removal. Implement tombstoning:

```python
# windows.py — tombstone tracker
class TombstoneTracker:
    TTL = 120  # seconds, matching SRV host_ttl
    def __init__(self, callback):
        self._seen: dict[str, float] = {}
        self._callback = callback
        threading.Thread(target=self._reap_loop, daemon=True).start()

    def on_browse_result(self, name: str):
        now = time.time()
        if name not in self._seen:
            self._callback(("added", name))
        self._seen[name] = now

    def _reap_loop(self):
        while True:
            time.sleep(30)
            cutoff = time.time() - self.TTL
            gone = [n for n, t in self._seen.items() if t < cutoff]
            for n in gone:
                del self._seen[n]
                self._callback(("removed", n))
```

---

## 6. Backend 4: Userspace Fallback

The existing python-zeroconf implementation, renamed and wrapped to implement `MdnsBackend`.

```python
# saturn/mdns/userspace.py
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, NonUniqueNameException

class UserspaceBackend:
    def __init__(self):
        self._zc = Zeroconf()

    def advertise(self, spec: AdvertiseSpec) -> None:
        info = ServiceInfo(
            type_="_saturn._tcp.local.",
            name=f"{spec.name}._saturn._tcp.local.",
            port=spec.port,
            addresses=[...],
            properties=spec.txt,
        )
        try:
            self._zc.register_service(info)
        except NonUniqueNameException:
            from .conflict import handle_conflict_userspace
            handle_conflict_userspace(spec, self)
```

**macOS note**: When `UserspaceBackend` is selected on macOS (i.e., never in normal
operation — only in fallback mode), log a `WARNING` explaining the RFC §11 violation
and that responses may be ignored by compliant implementations.

---

## 7. TXT Record Schema v2

### 7.1 Required Keys

| Key | Max len | Description |
|-----|---------|-------------|
| `v` | 3 | Protocol version — always `"2"` in v2 |
| `id` | 36 | Stable node UUID (RFC 4122, hex with hyphens) |
| `dep` | 7 | `"network"` or `"cloud"` |
| `api` | 10 | `"openai"` or `"ollama"` |
| `pri` | 5 | Priority integer as string |

### 7.2 Optional Keys

| Key | Max len | Description |
|-----|---------|-------------|
| `base` | 80 | Base URL for cloud deployments |
| `feat` | 30 | Feature flags: `"ephemeral_auth"`, `"network_proxy"` |
| `caps` | 40 | Comma-separated capabilities: `"chat,code,vision"` |
| `ctx` | 7 | Max context window as string |
| `cost` | 7 | `"free"`, `"paid"`, or `"unknown"` |
| `models` | 200 | Comma-separated model IDs (truncated, full list at `/v1/models`) |
| `mtrunc` | 1 | `"1"` if models list was truncated |

### 7.3 Node Identity

The `id=` key contains a UUID v4 generated **once** at first service start and persisted:

```python
# saturn/mdns/identity.py
import uuid
from pathlib import Path

_ID_FILE = Path.home() / ".saturn" / "node_id"

def get_node_id() -> str:
    if _ID_FILE.exists():
        return _ID_FILE.read_text().strip()
    nid = str(uuid.uuid4())
    _ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ID_FILE.write_text(nid)
    return nid
```

The UUID persists across service restarts, name conflict renames, and port changes. Clients
should key their internal state on `id`, not on instance name.

### 7.4 Total Size Budget

```
v=2             4 bytes
id=<uuid36>    39 bytes
dep=network    11 bytes
api=openai     10 bytes
pri=100         7 bytes
feat=network_proxy 18 bytes
caps=chat,code  14 bytes
ctx=8192        8 bytes
cost=free       9 bytes
models=...    200 bytes (budget)
--------------------------
TOTAL         320 bytes  (< 400-byte practical limit)
```

---

## 8. DNS-SD Subtype Registration

Register subtypes alongside the primary PTR record so role-specific browsing is possible
without downloading TXT records:

```
Primary:     _saturn._tcp.local.               PTR  "node._saturn._tcp.local."
Coordinator: _coordinator._sub._saturn._tcp.local.  PTR  "node._saturn._tcp.local."
Worker:      _worker._sub._saturn._tcp.local.        PTR  "node._saturn._tcp.local."
```

Saturn roles:

```python
# saturn/mdns/subtypes.py
ROLE_SUBTYPES = {
    "coordinator": "_coordinator",
    "worker": "_worker",
    "cloud": "_cloud",
    "beacon": "_beacon",
}

def subtypes_for_role(role: str) -> list[str]:
    return [ROLE_SUBTYPES[r] for r in [role] if r in ROLE_SUBTYPES]
```

A client browsing only coordinators queries `_coordinator._sub._saturn._tcp.local.` and
receives only coordinator PTR records, avoiding unnecessary SRV/TXT resolution for workers.

---

## 9. Conflict Resolution and Stable Identity

### 9.1 Conflict Handler

```python
# saturn/mdns/conflict.py
import logging, re
from pathlib import Path

_NAME_FILE = Path.home() / ".saturn" / "instance_name"
logger = logging.getLogger("saturn.mdns.conflict")

def get_instance_name(base: str) -> str:
    if _NAME_FILE.exists():
        return _NAME_FILE.read_text().strip()
    return base

def update_instance_name(new_name: str) -> None:
    _NAME_FILE.write_text(new_name)
    logger.warning(
        f"mDNS name conflict — renamed to '{new_name}'. "
        f"Stable node identity (id=) is unchanged."
    )

def next_name(name: str) -> str:
    m = re.match(r"^(.*)\s+\((\d+)\)$", name)
    if m:
        return f"{m.group(1)} ({int(m.group(2)) + 1})"
    return f"{name} (2)"
```

### 9.2 Conflict Detection During Operation

For the userspace backend, attach a `NameChanged` signal handler on the Avahi entry group
(or equivalent) and call `update_instance_name` + re-advertise:

```python
# In AvahiBackend._on_group_state:
elif state == avahi.ENTRY_GROUP_ESTABLISHED:
    # The actual registered name may have been renamed by Avahi
    actual_name = self._group.GetServiceName()
    if actual_name != self._current_spec.name:
        update_instance_name(actual_name)
```

---

## 10. Settle Detection

### 10.1 Avahi: AVAHI_BROWSER_ALL_FOR_NOW

```python
# AvahiBackend.browse():
self._settle = threading.Event()
browser_iface.connect_to_signal("AllForNow", self._settle.set)

def wait_for_settle(self, timeout: float = 5.0) -> None:
    self._settle.wait(timeout=timeout)
```

`AllForNow` fires when Avahi has flushed its local cache and sent the first PTR query and
received all cached responses. Subsequent events are pushed in real-time.

### 10.2 Bonjour: kDNSServiceFlagsMoreComing

```python
# BonjourBackend._browse_reply:
def _browse_reply(self, sd_ref, flags, ifindex, err, name, regtype, domain, ctx):
    more_coming = bool(flags & 0x1)  # kDNSServiceFlagsMoreComing
    self._on_service_event(flags, name)
    if not more_coming:
        self._settle.set()
```

`kDNSServiceFlagsMoreComing` absent means the daemon has dispatched its current batch.
The first time a browse callback fires without this flag, settle is complete.

### 10.3 Userspace Fallback

python-zeroconf does not expose a batch-completion signal. Use query-schedule-based settle:

```python
# After ServiceBrowser construction, the browser sends its first PTR query.
# RFC 6762 §5.2: no response arrives within 1s → exponential backoff begins.
# If services are present, their responses arrive within 300ms (RFC §6 timeout).
# Set settle after first query interval with a minimum floor:

def _settle_after_first_query(browser, settle_event):
    # Schedule settle 500ms after browser construction
    # (first query sent at t=0, responses arrive by t=300ms per RFC §6)
    import threading
    threading.Timer(0.5, settle_event.set).start()
```

### 10.4 `discover()` Replacement

```python
# saturn/mdns/discover.py
def discover(timeout: float = 5.0, backend: str | None = None) -> list[SaturnService]:
    mdns = make_backend(backend)
    services: dict[str, SaturnService] = {}
    settle = threading.Event()

    def on_event(event: ServiceEvent) -> None:
        action, record = event
        if action == "added":
            services[record.node_id] = build_service(record)  # keyed on stable UUID
        elif action == "removed":
            services.pop(record.node_id, None)

    mdns.browse(callback=on_event)
    mdns.wait_for_settle(timeout=timeout)
    mdns.stop_browse()
    mdns.close()
    return sorted(services.values(), key=lambda s: s.priority)
```

Services are keyed on `node_id` (the stable UUID), not instance name. This makes
`discover()` immune to rename events during the browse window.

---

## 11. Migration Path

### 11.1 Phase 1: Schema v2 with backward compat (non-breaking)

**Effort:** Small (discovery.py only)
**Risk:** Low

- Keep existing `SaturnAdvertiser` but add `id=get_node_id()` to `_properties()`
- Keep `version=1.0` for old-schema compatibility; add `v=2` as a new key
- Add `mtrunc=1` to `_properties()` when models list is truncated
- Existing v1 receivers ignore unknown TXT keys — safe

**Code change in `_properties()`:**
```python
return {
    'v': '2',
    'version': '1.0',   # backward compat
    'id': get_node_id(),
    'dep': self.deployment,        # renamed from 'deployment'
    'deployment': self.deployment, # backward compat
    ...
    'mtrunc': '1' if models_truncated else '',
}
```

### 11.2 Phase 2: Backend abstraction (non-breaking)

**Effort:** Medium (new files, refactor discovery.py)
**Risk:** Low (additive, existing path remains as userspace backend)

1. Create `saturn/mdns/` package with `backend.py`, `detect.py`, `identity.py`
2. Move existing `SaturnDiscovery` / `SaturnAdvertiser` to `saturn/mdns/userspace.py`
3. Add `AvahiBackend` and `BonjourBackend` as new files
4. Update `SaturnDiscovery` / `SaturnAdvertiser` in `discovery.py` to delegate to backend

### 11.3 Phase 3: Conflict handling

**Effort:** Small
**Risk:** Low

1. Create `saturn/mdns/conflict.py` with `get_instance_name`, `update_instance_name`
2. Catch `NonUniqueNameException` in `UserspaceBackend.advertise()` and trigger rename loop
3. Wire `AVAHI_ENTRY_GROUP_COLLISION` handler in `AvahiBackend`
4. Wire `kDNSServiceErr_NameConflict` handler in `BonjourBackend`

### 11.4 Phase 4: Settle detection cleanup

**Effort:** Small
**Risk:** Low

1. Add `wait_for_settle()` method to each backend
2. Replace `time_since_last >= settle_time` loop in `discover()` with `wait_for_settle()`
3. Remove `settle_time` parameter from `discover()` (keep as ignored kwarg for 1 release)
4. Remove `time.sleep()` from tests — replace with `wait_for_settle()`

### 11.5 Phase 5: DNS-SD subtypes

**Effort:** Small
**Risk:** Low

Add `subtypes` field to `SaturnAdvertiser.__init__()` and pass to backend. Consumers
that browse a specific subtype get it for free. Non-subtype consumers are unaffected.

---

## 12. Performance Targets

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| Service registration time (Linux) | ~2.5s (priority scan) | <500ms | Remove `_find_available_priority()` pre-scan; handle conflict after probe fails |
| Service registration time (macOS) | ~2.5s | <500ms | Same; Bonjour backend skips userspace socket setup |
| `discover()` first result latency | 300ms–1s | <300ms | `wait_for_settle()` returns on first `AllForNow` / `kDNSServiceFlagsMoreComing` absent |
| `discover()` total time (no peers) | 8s (hard timeout) | 2s | Settle detection + 2s fallback timeout (RFC: no response in 1s = no peers) |
| Test suite discovery time | 2.5s per test | <1s | Protocol-based settle, not sleep |
| TXT record parse round-trip | Opaque (library) | Same | No regression expected |

### 12.1 Startup time improvement

The current `_find_available_priority()` adds a 2-second mDNS scan on **every** service
start. Removing it and handling priority at the TXT level (priority is a soft preference,
not a uniqueness constraint — duplicates are fine) reduces startup time by 2 seconds
unconditionally.

---

## 13. Security Hardening

### 13.1 Avahi CVEs (2025–2026)

Three CVEs fixed in Avahi 0.9-rc3 (released 2026-01-27):

- **CVE-2025-68276**: Remote/local DoS via reachable assertion in browse path
- **CVE-2025-68468**: Remote DoS via malformed record in announce path
- **CVE-2025-68471**: Local DoS via entry group state machine assertion

**Mitigation for Saturn:**
- Saturn does not expose Avahi's D-Bus API to untrusted code
- Saturn's Avahi client runs as an unprivileged D-Bus client — it cannot trigger
  daemon-side assertions directly
- Ensure deployment environments run Avahi 0.9-rc3+ (add to deployment documentation)
- On Avahi 0.8 deployments: treat any `AvahiClientState.AVAHI_CLIENT_FAILURE` as a
  signal to fall back to userspace backend rather than crashing

```python
def _on_client_state(self, client, state, userdata):
    if state == avahi.CLIENT_FAILURE:
        logger.warning("Avahi daemon failure, falling back to userspace backend")
        self._fallback_to_userspace()
```

### 13.2 Beacon TXT Record — Ephemeral Key Size

`BeaconAdvertiser._properties()` (`runner.py:143-156`) emits the ephemeral API key in
the TXT record. TXT records are multicast to the entire link segment — anyone on the
network who can receive mDNS can read the key. This is by design (the key is ephemeral
and scoped to the calling process), but:

- Log a warning if key length > 240 bytes (already done at `runner.py:146-147`)
- Consider a TTL on the mDNS advertisement equal to the credential expiry time so caches
  don't serve expired keys. Currently this is not implemented — TXT records use the
  default 4500s TTL regardless of key expiry. Set `other_ttl` on the `ServiceInfo`:

```python
# In BeaconAdvertiser.register():
self._info = ServiceInfo(
    ...
    other_ttl=min(self.credential_manager.expiration_interval, 4500)
)
```

### 13.3 TXT Record Injection

Saturn builds TXT values from user-provided model names fetched from the upstream API
(`_fetch_models()` in `runner.py:286-306`). If a hostile upstream returns model names
containing `=`, newlines, or null bytes, these could corrupt TXT parsing on receivers.

Sanitize model names before inserting into TXT:

```python
def _sanitize_txt_value(v: str) -> str:
    return v.replace('=', '_').replace('\x00', '').replace('\n', '')[:63]
```

### 13.4 mDNS Packet Validation (Userspace Backend)

When running in userspace mode, Saturn receives raw mDNS packets. python-zeroconf handles
DNS wire-format parsing. Ensure the version in use is not vulnerable to known parsing CVEs.
As of zeroconf 0.148.0 no known CVEs apply, but pin the minimum version in `requirements.txt`:

```
zeroconf>=0.131.0,<1.0.0  # pin to known-good minor range
```

### 13.5 RFC 6762 §11 TTL=255 Check

python-zeroconf does not verify that incoming mDNS packets have TTL=255 in the IP header
(RFC 6762 §11: packets with TTL < 255 SHOULD be discarded). This means a remote attacker
on a different subnet who can forge UDP source addresses could potentially inject mDNS
responses. This is partially mitigated by the link-local scope of multicast routing
(routers don't forward TTL=1 multicast), but defense in depth would add the TTL check.

This is a python-zeroconf limitation. File an upstream issue if this is a concern; the
fix requires `IP_RECVTTL` + ancillary data handling.
