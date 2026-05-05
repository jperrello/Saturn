"""Saturn-cbt.7 / §17.G.3 — IPv6 / dual-stack schema fields.

Per PRE_SPECS_B3.md §17.G.3.2. Both `ServiceRecord` (saturn/mdns/backend.py:6)
and `SaturnService` (saturn/discovery.py:75) MUST gain address-plural fields:

  ServiceRecord.addresses: list[str] = field(default_factory=list)
  SaturnService.addresses: list[str] = field(default_factory=list)
  SaturnService.ipv6:      Optional[str] = None

`addresses` carries every resolved A and AAAA address (textual form);
`ipv6` is a convenience pointing at the first AAAA if any.

This contract pins the schema-level surface only. Per-backend resolve
plumbing (userspace `info.addresses` walk for v4/v6, Bonjour
`DNSServiceGetAddrInfo`, Avahi protocol-specific browse) is the larger
implementation surface and is filed as **cbt.7.resolve** sub-bead.

NO MOCKS. Pure dataclass introspection — no network.
"""

import dataclasses

import pytest


def test_servicerecord_has_addresses_list_field():
    from saturn.mdns.backend import ServiceRecord
    fields = {f.name: f for f in dataclasses.fields(ServiceRecord)}
    assert "addresses" in fields, (
        "ServiceRecord must add `addresses: list[str] = field(default_factory=list)` "
        "per §17.G.3.2 to carry both A and AAAA records resolved from a peer. "
        f"Current fields: {sorted(fields.keys())!r}"
    )
    rec = ServiceRecord(name="x", node_id="x", host="127.0.0.1", port=1, txt={})
    assert isinstance(rec.addresses, list), (
        f"ServiceRecord.addresses must default to a list (factory); "
        f"got {type(rec.addresses).__name__}"
    )
    assert rec.addresses == [], (
        f"ServiceRecord.addresses must default to []; got {rec.addresses!r}"
    )


def test_saturnservice_has_addresses_and_ipv6_fields():
    from saturn.discovery import SaturnService
    fields = {f.name: f for f in dataclasses.fields(SaturnService)}
    missing = [f for f in ("addresses", "ipv6") if f not in fields]
    assert not missing, (
        f"SaturnService must add fields {missing!r} per §17.G.3.2: "
        f"`addresses: list[str] = field(default_factory=list)` and "
        f"`ipv6: Optional[str] = None`. "
        f"Current fields: {sorted(fields.keys())!r}"
    )
    s = SaturnService(name="x", host="127.0.0.1", port=1)
    assert isinstance(s.addresses, list) and s.addresses == [], (
        f"SaturnService.addresses must default to []; got {s.addresses!r}"
    )
    assert s.ipv6 is None, (
        f"SaturnService.ipv6 must default to None; got {s.ipv6!r}"
    )


def test_servicerecord_addresses_accepts_dual_stack_strings():
    from saturn.mdns.backend import ServiceRecord
    rec = ServiceRecord(
        name="x", node_id="x", host="192.168.1.10", port=1, txt={},
        addresses=["192.168.1.10", "fe80::1"],
    )
    assert "192.168.1.10" in rec.addresses, "v4 addr must be retained"
    assert "fe80::1" in rec.addresses, "v6 addr must be retained alongside v4"
