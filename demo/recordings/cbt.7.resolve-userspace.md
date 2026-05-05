# cbt.7.resolve — userspace `_resolve()` walks v4 + v6

**Bead:** Saturn-1xh   **Commit:** `0ccab52`

`saturn/mdns/userspace.py::_resolve()` previously took
`info.addresses[0]` and ran it through `socket.inet_ntoa` —
v4-only by construction; any AAAA the advertiser registered was
silently dropped on the floor.

Fix: source `info.addresses_by_version(IPVersion.All)` and dispatch
per entry — 4-byte → `inet_ntoa`, 16-byte → `inet_ntop(AF_INET6)`.
The returned `ServiceRecord.addresses` is now the full list (v4 +
v6 in advertise order); `.host` stays as the first entry so existing
`service.host` callers keep working unchanged.

Bonjour (`saturn/mdns/bonjour.py`) and Avahi
(`saturn/mdns/avahi.py`) resolve plumbing is explicitly out of scope
and tracks separately under `cbt.7.resolve.bonjour` /
`cbt.7.resolve.avahi`.

## Reproducer (real Zeroconf, dual-stack registration on `127.0.0.1` + `::1`)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_dual_stack_resolve_cbt7_resolve.py
```

The test registers a single service with both an A and an AAAA record
through a real Zeroconf instance, then calls the userspace
`_resolve()` and asserts `ServiceRecord.addresses` contains both
families. Falsifies the v4-only regression directly.

## Captured output

```text
saturn/tests/test_dual_stack_resolve_cbt7_resolve.py::
test_userspace_resolve_returns_both_v4_and_v6_addresses PASSED            [100%]
========================= 1 passed, 1 warning in 2.02s ============================
```

## Where this fits in the dual-stack chain

  - **cbt.7** (`d30e014`) — schema-only carrier: `addresses[]` + `ipv6`
    fields on `ServiceRecord` / `SaturnService`.
  - **cbt.7.resolve** (`0ccab52`) — userspace resolver populates the
    plural fields end-to-end.   ← this bead
  - **cbt.7.resolve.bonjour / .avahi** — pending.
  - **cbt.7.advertise** — advertise-side AAAA (separate ship).
  - **cbt.7.dedup** — same-node_id v4+v6 events merge instead of
    double-listing.
  - **cbt.7.prefer** — `connect_address()` picks v6 when both available
    (`SATURN_PREFER_V6`).

cbt.7.resolve is the link that makes the schema-only field actually
fill on the userspace path; without it, the rest of the chain has
nothing to read.
