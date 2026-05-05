"""Saturn-cbt.5 / §17.G.1 — AP isolation detection probe.

Per PRE_SPECS_B3.md §17.G.1.2. New module `saturn/mdns/isolation.py` MUST
expose:

  @dataclass
  class IsolationProbe:
      advertising: bool
      self_seen: bool
      peers_seen: int
      ifaces_with_link: List[str]
      suspected_ap_isolation: bool
      diagnosis: str

  def probe(timeout: float = 4.0) -> IsolationProbe: ...

Behavior: `probe()` advertises a transient `_saturn-probe._tcp.local.` record
on a random port and browses for it from the same process. On a healthy
loopback / LAN, the probe MUST report `self_seen=True`.

This contract pins the public-surface shape and the loopback-roundtrip
invariant. The Web-UI / `/api/discover` integration (§17.G.1.3) is out of
scope here; file as **cbt.5.web** when isolation.py lands.

NO MOCKS. The probe is exercised against the real loopback multicast group.
"""

import pytest


def _iso():
    try:
        return __import__("saturn.mdns.isolation", fromlist=["probe", "IsolationProbe"])
    except ImportError as e:
        pytest.fail(
            "module saturn/mdns/isolation.py does not exist. "
            "Create it per PRE_SPECS_B3.md §17.G.1.2 with: "
            "IsolationProbe dataclass (advertising, self_seen, peers_seen, "
            "ifaces_with_link, suspected_ap_isolation, diagnosis), "
            "and probe(timeout=4.0) -> IsolationProbe. "
            f"Raw import error: {e}"
        )


def test_isolation_probe_module_surface():
    iso = _iso()
    assert hasattr(iso, "probe"), "module must expose probe(timeout=...) -> IsolationProbe"
    assert hasattr(iso, "IsolationProbe"), "module must expose IsolationProbe dataclass"
    fields = getattr(iso.IsolationProbe, "__dataclass_fields__", None)
    assert fields is not None, "IsolationProbe must be a @dataclass"
    expected = {"advertising", "self_seen", "peers_seen", "ifaces_with_link",
                "suspected_ap_isolation", "diagnosis"}
    missing = expected - set(fields.keys())
    assert not missing, f"IsolationProbe missing fields: {sorted(missing)!r}"


@pytest.mark.timeout(15)
def test_loopback_probe_self_seen_is_true():
    iso = _iso()
    result = iso.probe(timeout=4.0)
    assert isinstance(result, iso.IsolationProbe), (
        f"probe() must return IsolationProbe; got {type(result).__name__}"
    )
    assert result.advertising is True, (
        f"probe() must advertise its transient probe record; "
        f"advertising={result.advertising!r}, diagnosis={result.diagnosis!r}"
    )
    assert result.self_seen is True, (
        f"probe() on a normal loopback must observe its own advertised probe "
        f"record (self_seen=True); got self_seen={result.self_seen!r}, "
        f"diagnosis={result.diagnosis!r}. If self_seen is False even on loopback, "
        f"either the probe browser timeout is too tight or the listener is not "
        f"binding to the loopback multicast group."
    )
    assert result.suspected_ap_isolation is False, (
        f"loopback should not be flagged as AP-isolated; "
        f"suspected_ap_isolation={result.suspected_ap_isolation!r}, "
        f"diagnosis={result.diagnosis!r}"
    )
