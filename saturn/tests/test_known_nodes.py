import json
import os
import threading

import pytest

from saturn.mdns import known_nodes
from saturn.mdns.backend import ServiceRecord
from saturn import discovery as disc


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    p = tmp_path / "known_nodes.json"
    monkeypatch.setattr(known_nodes, "PATH", p)
    monkeypatch.setattr(known_nodes, "_warned_mode", False)
    disc.set_trust_policy("tofu", [])
    yield


def _disc():
    return disc.SaturnDiscovery(backend=False)


def _rec(name, node_id, host="10.0.0.1", port=8080, priority=50):
    return ServiceRecord(
        name=name,
        node_id=node_id,
        host=host,
        port=port,
        txt={"priority": str(priority), "version": "1.0"},
    )


def test_tofu_first_contact_pin():
    d = _disc()
    d._add(_rec("ollama", "uuid-A"))
    assert known_nodes.known_node_id("ollama") == "uuid-A"
    state = known_nodes.load()
    first = state["nodes"]["ollama"]["first_seen"]
    d2 = _disc()
    d2._add(_rec("ollama", "uuid-A", host="10.0.0.2"))
    state2 = known_nodes.load()
    assert state2["nodes"]["ollama"]["first_seen"] == first
    assert state2["nodes"]["ollama"]["host_seen"] == "10.0.0.2"


def test_silent_rebind_refused():
    d = _disc()
    d._add(_rec("ollama", "uuid-A", priority=50))
    d._add(_rec("ollama", "uuid-B", priority=0, host="10.0.0.99"))
    best = d.get_best_service()
    assert best is not None
    assert best.node_id == "uuid-A"
    rejected = known_nodes.load()["rejected"]
    assert any(r["node_id"] == "uuid-B" for r in rejected)


def test_lower_priority_rebind_still_rejected():
    d = _disc()
    d._add(_rec("ollama", "uuid-A", priority=50))
    d._add(_rec("ollama", "uuid-B", priority=60))
    all_svcs = d.get_all_services()
    assert [s.node_id for s in all_svcs] == ["uuid-A"]
    b_records = [s for s in d.services.values() if s.node_id == "uuid-B"]
    assert b_records and b_records[0].trust == "rebind_rejected"


def test_allowlist_mode():
    disc.set_trust_policy("allowlist", ["uuid-A"])
    d = _disc()
    d._add(_rec("ollama", "uuid-A", priority=50))
    d._add(_rec("ollama", "uuid-B", priority=0))
    best = d.get_best_service()
    assert best is not None and best.node_id == "uuid-A"


def test_attest_path():
    d = _disc()
    d._add(_rec("ollama", "uuid-A"))
    d._add(_rec("ollama", "uuid-B", host="10.0.0.99"))
    known_nodes.attest("ollama", "uuid-B", "10.0.0.99")
    assert known_nodes.known_node_id("ollama") == "uuid-B"
    d.reclassify_all()
    b = next(s for s in d.services.values() if s.node_id == "uuid-B")
    assert b.trust == "pinned"


def test_mode_flip_live_update():
    d = _disc()
    d._add(_rec("ollama", "uuid-A", priority=50))
    d._add(_rec("ollama", "uuid-B", priority=0))
    assert d.get_best_service().node_id == "uuid-A"
    disc.set_trust_policy("open", [])
    d.reclassify_all()
    assert d.get_best_service().node_id == "uuid-B"


def test_file_mode_refusal():
    known_nodes.pin("ollama", "uuid-A", "10.0.0.1")
    os.chmod(known_nodes.PATH, 0o644)
    assert known_nodes.known_node_id("ollama") is None
    d = _disc()
    d._add(_rec("ollama", "uuid-X"))
    assert d.services
    only = list(d.services.values())[0]
    assert only.trust in ("first_seen", "pinned", "unknown")


def test_concurrency_pin_idempotent():
    barrier = threading.Barrier(8)
    def hit():
        barrier.wait()
        known_nodes.pin("ollama", "uuid-A", "10.0.0.1")
    threads = [threading.Thread(target=hit) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    state = known_nodes.load()
    assert state["nodes"]["ollama"]["node_id"] == "uuid-A"
    assert "first_seen" in state["nodes"]["ollama"]
