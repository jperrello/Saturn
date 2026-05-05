"""Saturn-7sg / cbt.7.dedup — dual-stack address dedup in SaturnDiscovery.

Per PRE_SPECS_B3.md §17.G.3.3 and §17.G.3.6. When the same logical service
(same node_id + name) is reported via two address-family records — once
with a v4 address, once with a v6 — `SaturnDiscovery._add()` MUST merge
their `addresses` fields rather than overwrite, so the final stored
`SaturnService` lists BOTH families.

Today (`saturn/discovery.py:228`) the second event blindly does
`self.services[key] = service`, dropping the v4 address that the first
event captured. Result: callers reading `service.addresses` see only
whichever family was reported last.

Falsifiable oracle: feed two synthetic `ServiceRecord` events into the
same `SaturnDiscovery` instance — first carrying addresses=["v4"], second
carrying addresses=["v6"]. After both events, the resolved
`SaturnService.addresses` MUST contain both v4 and v6 strings.

NO MOCKS. `SaturnDiscovery(backend=False)` skips backend init; events are
fed directly to `_on_event()`.
"""

import pytest

from saturn.discovery import SaturnDiscovery
from saturn.mdns.backend import ServiceRecord


pytestmark = pytest.mark.timeout(10)


def test_dual_stack_events_dedup_into_merged_addresses():
    d = SaturnDiscovery(backend=False)

    common = dict(
        name="dedup-test",
        node_id="abcd1234",
        port=8080,
        txt={"version": "1.0", "id": "abcd1234"},
    )

    rec_v4 = ServiceRecord(host="192.168.1.10", addresses=["192.168.1.10"], **common)
    rec_v6 = ServiceRecord(host="fe80::1",      addresses=["fe80::1"],      **common)

    d._on_event(("added", rec_v4))
    d._on_event(("updated", rec_v6))

    services = d.get_all_services()
    matches = [s for s in services if s.name == "dedup-test"]
    assert len(matches) == 1, (
        f"two events for the same (node_id, name) must collapse into one "
        f"SaturnService entry; got {len(matches)} match(es): "
        f"{[(s.name, s.host, s.addresses) for s in matches]!r}"
    )
    s = matches[0]
    assert "192.168.1.10" in s.addresses, (
        f"v4 address from the first event must be retained after the second "
        f"(updated) event; got addresses={s.addresses!r}. Per §17.G.3.3 "
        f"_add() must merge addresses, not overwrite the SaturnService."
    )
    assert "fe80::1" in s.addresses, (
        f"v6 address from the second event must also be present; "
        f"got addresses={s.addresses!r}"
    )
