"""Saturn-an5 / cbt.3.d.sweep — active liveness sweep on SaturnDiscovery.

Per DISCOVERY_AUDIT.md (d) note 2 (cross-cuts cbt.4). The shipped
`SaturnService.last_seen` (Saturn-cbt.3.d, green) gives consumers a way to
filter zombies but `SaturnDiscovery` itself does not actively probe peers
for liveness — entries persist until the underlying mDNS library happens
to evict them (default zeroconf record TTL is 120s+, Bonjour ~75 min).

This contract pins the active sweep: `SaturnDiscovery` MUST expose a
public method `sweep_stale(max_age: float)` (or similar) that drops
entries whose `last_seen` is older than `max_age`. After calling
`sweep_stale(0.0)` immediately after a fresh add, no entries remain
younger than 0s; therefore all entries are evicted.

A more useful invariant: entries added at `t=0` with `sweep_stale(max_age=0.5)`
called at `t=0.6` MUST be evicted; entries added at `t=0.5` MUST NOT.

The cbt.4 health-loop (Saturn-cbt.4 / `_failover_state`) lives elsewhere;
this contract pins ONLY the in-memory eviction surface, not the network
probe. File **Saturn-an5.probe** for the actual `/v1/health` integration
once both this and the cbt.4 sweep loop are in place.

NO MOCKS. Pure in-memory state on `SaturnDiscovery(backend=False)`.
"""

import time

import pytest

from saturn.discovery import SaturnDiscovery
from saturn.mdns.backend import ServiceRecord


pytestmark = pytest.mark.timeout(10)


def _add(d, name, node_id="x"):
    d._on_event(("added", ServiceRecord(
        name=name, node_id=node_id, host="127.0.0.1", port=8080,
        txt={"version": "1.0", "id": node_id},
    )))


def test_sweep_stale_drops_old_entries_keeps_fresh_ones():
    d = SaturnDiscovery(backend=False)

    _add(d, "old-svc", node_id="o")
    older_seen_at = time.time()
    time.sleep(0.6)
    _add(d, "new-svc", node_id="n")

    if not hasattr(d, "sweep_stale"):
        pytest.fail(
            "SaturnDiscovery must expose a `sweep_stale(max_age)` method that "
            "drops entries whose last_seen is older than max_age. Per "
            "DISCOVERY_AUDIT.md (d) note 2, this is the in-memory side of the "
            "active liveness sweep; pair it with /v1/health probing in a "
            "follow-up bead."
        )
    d.sweep_stale(max_age=0.4)

    services = d.get_all_services()
    names = {s.name for s in services}
    assert "old-svc" not in names, (
        f"sweep_stale(max_age=0.4) must evict 'old-svc' (added ~0.6s ago); "
        f"remaining names={sorted(names)!r}"
    )
    assert "new-svc" in names, (
        f"sweep_stale must keep 'new-svc' (added <0.4s ago); "
        f"remaining names={sorted(names)!r}"
    )
