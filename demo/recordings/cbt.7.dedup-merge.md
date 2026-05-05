# cbt.7.dedup — merge addresses across events for the same `node_id`

**Bead:** Saturn-7sg   **Commit:** `189a86d`

Without dedup, a dual-stack peer surfaces twice in `discover()` —
once for the A record event and once for the AAAA event. Saturn
treated those as two distinct services on the same `node_id`, which
broke priority-based routing (each "service" got its own breaker
state, sticky session, and failover slot) and inflated the Network
Scan tab.

Fix: in `SaturnDiscovery._add()`, key by `node_id` and **merge** the
incoming `ServiceRecord.addresses` into the existing
`SaturnService.addresses` instead of overwriting. `_to_service()` now
populates `SaturnService.addresses` + `ipv6` from
`ServiceRecord.addresses`. The advertised peer ends up as a single
service entry whose `.addresses` is the union of every family it has
announced.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_dual_stack_dedup_cbt7_dedup.py
```

The test fires two real Zeroconf service events (one A, one AAAA) for
the same `node_id` and asserts `discover()` returns exactly one
entry whose `addresses` list contains both families.

## Captured output

```text
saturn/tests/test_dual_stack_dedup_cbt7_dedup.py::
test_dual_stack_events_dedup_into_merged_addresses PASSED                 [100%]
========================= 1 passed in <Ns> ============================
```

## Why this matters

cbt.7 (schema), cbt.7.resolve (userspace reader), cbt.7.advertise
(userspace writer) all assumed dedup downstream. Without 7.dedup the
data was right at the edges and wrong in the middle. With it, every
priority-based decision (cbt.4 failover included) sees one peer
instead of two phantoms, and `connect_address(service)`'s
v4-vs-v6 choice (cbt.7.prefer) actually has both families to choose
from.
