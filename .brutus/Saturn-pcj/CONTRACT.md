# CONTRACT — Saturn-pcj / cbt.6.userspace (= geoff's cbt.6.1): wire `routable_addrs()` into `UserspaceBackend.advertise`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.
**Geoff cite:** `PARITY_REVIEW_MAY05.md` §(c) NEW Saturn-cbt.6.1.

## Spec restatement (falsifiable)

`saturn/mdns/userspace.py:121-138`'s `UserspaceBackend.advertise()` must
source its `ServiceInfo.addresses` list from
`saturn.mdns.interfaces.routable_addrs()` per §17.G.2.3, replacing the
current single-IP `get_lan_ip()` shortcut. Geoff's exact change:

```python
addrs = [socket.inet_aton(ip) for ip in routable_addrs()] \
        or [socket.inet_aton(get_lan_ip())]
info = ServiceInfo(..., addresses=addrs, ...)
```

The fallback to `get_lan_ip()` ensures parity when `routable_addrs()`
returns an empty list (no UP non-loopback NICs).

## Test files

- `saturn/tests/test_userspace_multi_addr_cbt6_userspace.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_userspace_multi_addr_cbt6_userspace.py --no-header -rN --tb=short
```

## Captured red

```
saturn/tests/test_userspace_multi_addr_cbt6_userspace.py:62: AssertionError:
  routable_addrs() reported ['192.168.50.10','192.168.60.10'] but
  ServiceInfo.addresses only carries ['192.168.1.13']. UserspaceBackend.advertise
  must source its address list from saturn.mdns.interfaces.routable_addrs()
  (per §17.G.2.3), not the single-IP get_lan_ip() shortcut.
========================= 1 failed, 1 warning in 2.19s =========================
```

Transcript: `.brutus/Saturn-pcj/transcript.md`.

## Oracle

Test injects two synthetic addresses into `routable_addrs` (test-boundary
control of Saturn's own helper, not a mock of an external service); then
`UserspaceBackend.advertise(spec)` is called and `backend._info.addresses`
inspected. Both injected addresses MUST be present (decoded back from
4-byte form via `socket.inet_ntoa`).

## Out of scope

- Real multi-NIC integration via qj5.7 harness (geoff's stretch test in
  cbt.6.1 hand-off). File as **Saturn-pcj.harness** if the qj5.7 multi-NIC
  scaffold lands.
- IPv6 advertising — that is **Saturn-9rv** (cbt.7.advertise / cbt.7.2);
  this contract pins the multi-v4 path only.
- `SATURN_ADVERTISE_ALL` env opt-out — file under cbt.G.cfg.
- Bonjour / Avahi backends — they already advertise on all interfaces via
  daemon; no change per §17.G.2.3.

## Implementer

athena → hardener. ETA ~10 min.
