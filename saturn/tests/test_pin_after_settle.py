"""Saturn-qj5.16.13.3 — defer TOFU pin until SettleDetector quiet (or ≥2 confirmations).

Per SECURITY_AUDIT.md §15.2.b + §15.7. Today `saturn/discovery.py:_add` calls
`known_nodes.pin()` immediately when service.trust == "first_seen". An attacker
who times their priority-0 advertisement to arrive first during a fresh-install
discovery startup grabs the TOFU pin.

Spec: defer the pin to either
  (i)  after the SettleDetector signals quiet, OR
  (ii) only when the same (name, node_id) pair has been observed ≥2 times within
       the settle window.

Falsifier:
  - A single first-seen observation auto-pins → BAD.
  - Two competing node_ids for the same name within the settle window auto-pin
    either of them → BAD.
  - A single stable announce, repeated multiple times within the settle window,
    never pins → BAD (over-correction; legitimate flows must still TOFU).
"""

import json
import threading

import pytest

from saturn.mdns.backend import ServiceRecord


def _record(name, node_id, host="192.168.1.10", port=8080, priority=50, **txt):
    base = {
        "version": "1.0",
        "dep": "network",
        "api_type": "openai",
        "priority": str(priority),
    }
    base.update({k: str(v) for k, v in txt.items()})
    return ServiceRecord(name=name, node_id=node_id, host=host, port=port, txt=base)


@pytest.fixture
def known_nodes_isolated(tmp_path, monkeypatch):
    """Point known_nodes.PATH at an isolated tmp file so the test never reads/writes ~/.saturn/."""
    import saturn.mdns.known_nodes as kn
    fake = tmp_path / "known_nodes.json"
    fake.write_text(json.dumps({"version": 1, "nodes": {}, "rejected": []}))
    monkeypatch.setattr(kn, "PATH", fake)
    monkeypatch.setattr(kn, "_safe_mode", lambda: True)
    return kn


@pytest.fixture
def discoverer(monkeypatch):
    """Construct a SaturnDiscovery with no real backend."""
    import saturn.discovery as discovery
    monkeypatch.setattr(discovery, "_trust_mode", "tofu", raising=False)
    monkeypatch.setattr(discovery, "_allowlist", set(), raising=False)
    return discovery.SaturnDiscovery(backend=False)


# --- 1. Single first-seen observation must NOT pin during settle window ---

def test_single_first_seen_does_not_pin_during_settle(known_nodes_isolated, discoverer):
    rec = _record("svc-fresh", node_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    discoverer._add(rec)
    pinned = known_nodes_isolated.known_node_id("svc-fresh")
    assert pinned is None, (
        f"first observation must defer the pin per §15.2.b — got pinned={pinned!r}. "
        f"The current implementation calls known_nodes.pin() immediately, which lets an "
        f"attacker grab the TOFU slot by racing the honest server."
    )


# --- 2. Competing node_ids in settle window must block the pin ---

def test_competing_node_ids_in_settle_window_block_pin(known_nodes_isolated, discoverer):
    """Attacker (priority-0) arrives first; honest server (priority-50) arrives within ms.
    Neither must be pinned — the conflict is the signal that the settle window is unstable."""
    attacker = _record("svc-contested", node_id="11111111-1111-1111-1111-111111111111", priority=0)
    honest   = _record("svc-contested", node_id="99999999-9999-9999-9999-999999999999", priority=50)
    discoverer._add(attacker)
    discoverer._add(honest)
    pinned = known_nodes_isolated.known_node_id("svc-contested")
    assert pinned is None, (
        f"with two competing node_ids in the settle window, no pin must stick. "
        f"got pinned={pinned!r}. Either node_id was wrongly TOFU-trusted."
    )


def test_attacker_first_does_not_grab_pin(known_nodes_isolated, discoverer):
    """The attacker's race-to-first MUST NOT result in their node_id being pinned."""
    attacker_id = "11111111-1111-1111-1111-111111111111"
    honest_id   = "99999999-9999-9999-9999-999999999999"
    discoverer._add(_record("svc-race", node_id=attacker_id, priority=0))
    discoverer._add(_record("svc-race", node_id=honest_id,   priority=50))
    pinned = known_nodes_isolated.known_node_id("svc-race")
    assert pinned != attacker_id, (
        f"attacker grabbed TOFU pin by arriving first: pinned={pinned!r}. "
        f"§15.2.b mitigation must defer the pin so the priority-0 race fails."
    )


# --- 3. Stable single-source observation eventually pins (per §15.7 — TOFU still works) ---

def test_stable_single_source_pins_after_confirmations(known_nodes_isolated, discoverer):
    """A single stable announce repeated within the settle window must eventually pin —
    either after the SettleDetector signals quiet OR after the ≥2-confirmations heuristic.
    Without this, legitimate fresh-install TOFU never converges."""
    node = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    for _ in range(5):
        discoverer._add(_record("svc-stable", node_id=node))

    # Trigger settle if the implementation exposes a hook; tolerate both shapes.
    import saturn.discovery as discovery
    if hasattr(discovery, "_settle_for_test") and callable(discovery._settle_for_test):
        discovery._settle_for_test("svc-stable")
    elif hasattr(discoverer, "_settle"):
        try: discoverer._settle.signal()
        except Exception: pass

    pinned = known_nodes_isolated.known_node_id("svc-stable")
    assert pinned == node, (
        f"a stable single-source announce must pin once settle/quiet signals or after "
        f"≥2 confirmations. got pinned={pinned!r}, expected {node!r}. "
        f"Implementer: expose `saturn.discovery._settle_for_test(name)` or "
        f"`SaturnDiscovery._settle.signal()` so the test can drive the quiet step "
        f"without sleeping for the SettleDetector timeout."
    )


# --- 4. After deferral resolves, attacker's late conflict is rejected, not silently re-pinned ---

def test_late_conflict_after_pin_is_rebind_rejected(known_nodes_isolated, discoverer):
    """Once an honest pin lands (per test 3), a subsequent advertisement with a different
    node_id for the same service name must be classified rebind_rejected, not silently re-pinned."""
    honest = "99999999-9999-9999-9999-999999999999"
    for _ in range(5):
        discoverer._add(_record("svc-pinned-then-attacked", node_id=honest))

    import saturn.discovery as discovery
    if hasattr(discovery, "_settle_for_test"):
        discovery._settle_for_test("svc-pinned-then-attacked")
    elif hasattr(discoverer, "_settle"):
        try: discoverer._settle.signal()
        except Exception: pass

    assert known_nodes_isolated.known_node_id("svc-pinned-then-attacked") == honest, (
        "preflight: honest pin must land before this test exercises the late-conflict path"
    )

    attacker = "11111111-1111-1111-1111-111111111111"
    discoverer._add(_record("svc-pinned-then-attacked", node_id=attacker, priority=0))

    still_pinned = known_nodes_isolated.known_node_id("svc-pinned-then-attacked")
    assert still_pinned == honest, (
        f"after settle pinned the honest node_id, a late attacker advertisement must NOT "
        f"replace the pin. got pinned={still_pinned!r}, expected {honest!r}."
    )

    rejected = known_nodes_isolated.load().get("rejected", [])
    matched = [r for r in rejected if r.get("service_name") == "svc-pinned-then-attacked"
                                       and r.get("node_id") == attacker]
    assert matched, (
        f"late conflict must be recorded as rebind_rejected; rejected={rejected!r}"
    )
