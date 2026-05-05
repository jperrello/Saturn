"""Saturn-93w — TOFU pin-race (P1).

Per FAILOVER_SECURITY.md §(A). Saturn's TOFU has no operator-assertable
override: a hostile peer that registers a service-name + arbitrary
`node_id` BEFORE the legit peer comes online gets the name pinned
permanently. Subsequent legit advertisements with the correct node_id are
silently filtered to `rebind_rejected` and disappear from
`get_all_services()`. Operator has no signal, no UI, no recourse short of
manually editing `~/.saturn/known_nodes.json`.

Geoff's recommended fix: an operator-asserted name → node_id allowlist at
`~/.saturn/allowlist.json`, consulted by `_classify_trust` BEFORE the
TOFU promotion logic. Behavior:

  - name in allowlist, advertised node_id matches → "allowlist"
    (selectable, immediate; no two-confirmation warmup needed).
  - name in allowlist, advertised node_id MISMATCHES → "rebind_rejected"
    (refused, even if it's the first ever sighting; even if known_nodes
    has a stale TOFU pin from earlier).
  - name NOT in allowlist → existing TOFU flow unchanged.

Falsifiable oracles:

  1. With `{"foo": "LEGIT"}` in allowlist.json, classifying a service
     `(name=foo, node_id=ATTACKER)` MUST return `"rebind_rejected"`.
  2. With the same allowlist, classifying `(name=foo, node_id=LEGIT)`
     MUST return `"allowlist"` or `"pinned"` (either is acceptable;
     either makes the service selectable).
  3. Even when `known_nodes.pin()` has previously stored
     `foo → ATTACKER` (the pin-race outcome), the allowlist override
     classifies `(foo, ATTACKER)` as `"rebind_rejected"` and does NOT
     leave `"pinned"`.

Tests monkeypatch the runtime path via a module attribute the
implementation MUST expose: `saturn.discovery.ALLOWLIST_PATH` (a
`pathlib.Path`). Tests also expect an optional `reload_allowlist()`
helper if the implementation caches.

NO MOCKS. Pure file-system + in-process classifier.
"""

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.timeout(15)


def _attempt_reload():
    """Re-read the allowlist file if the implementation caches it."""
    import saturn.discovery as D
    if hasattr(D, "reload_allowlist"):
        D.reload_allowlist()


@pytest.fixture
def allowlist_isolated(tmp_path, monkeypatch):
    """Point both known_nodes.PATH and ALLOWLIST_PATH at tmp_path so the
    test cannot collide with the user's real ~/.saturn/."""
    sat_dir = tmp_path / ".saturn"
    sat_dir.mkdir()

    import saturn.mdns.known_nodes as KN
    monkeypatch.setattr(KN, "PATH", sat_dir / "known_nodes.json")

    import saturn.discovery as D
    if not hasattr(D, "ALLOWLIST_PATH"):
        pytest.fail(
            "saturn.discovery must expose `ALLOWLIST_PATH: pathlib.Path` so "
            "operators can preseed name → node_id assertions per geoff's "
            "FAILOVER_SECURITY.md §(A) P1 fix. Today the constant is "
            "missing; the operator has no override path."
        )
    monkeypatch.setattr(D, "ALLOWLIST_PATH", sat_dir / "allowlist.json")
    return sat_dir


def _service(name, node_id, host="192.168.1.10", port=8080):
    from saturn.discovery import SaturnService
    return SaturnService(name=name, host=host, port=port, node_id=node_id)


def test_allowlist_rejects_attacker_node_id_for_known_name(allowlist_isolated):
    (allowlist_isolated / "allowlist.json").write_text(
        json.dumps({"foo": "LEGIT"})
    )
    _attempt_reload()
    from saturn.discovery import _classify_trust
    trust = _classify_trust(_service("foo", "ATTACKER"))
    assert trust == "rebind_rejected", (
        f"with allowlist {{foo: LEGIT}} pre-seeded, classifying "
        f"(name=foo, node_id=ATTACKER) MUST return 'rebind_rejected' "
        f"(filtered from selectable set). Got {trust!r}. The TOFU "
        f"first_seen logic must consult ALLOWLIST_PATH BEFORE the "
        f"known_nodes pin lookup, so a hostile peer cannot win the race."
    )


def test_allowlist_accepts_matching_node_id(allowlist_isolated):
    (allowlist_isolated / "allowlist.json").write_text(
        json.dumps({"foo": "LEGIT"})
    )
    _attempt_reload()
    from saturn.discovery import _classify_trust
    trust = _classify_trust(_service("foo", "LEGIT"))
    assert trust in ("allowlist", "pinned"), (
        f"with allowlist {{foo: LEGIT}} pre-seeded, classifying "
        f"(name=foo, node_id=LEGIT) MUST return 'allowlist' or 'pinned' "
        f"(selectable). Got {trust!r}."
    )


def test_allowlist_overrides_stale_tofu_pin(allowlist_isolated):
    """The pin-race attack: hostile node_id was already TOFU-pinned earlier
    (because it advertised first). Operator-asserted allowlist now lists
    the legitimate node_id. Hostile must be rejected even though it's
    'pinned' in known_nodes.json."""
    import saturn.mdns.known_nodes as KN
    KN.pin("foo", "ATTACKER", "192.168.1.99")  # simulate the race outcome

    (allowlist_isolated / "allowlist.json").write_text(
        json.dumps({"foo": "LEGIT"})
    )
    _attempt_reload()
    from saturn.discovery import _classify_trust
    trust = _classify_trust(_service("foo", "ATTACKER"))
    assert trust == "rebind_rejected", (
        f"allowlist {{foo: LEGIT}} MUST override a stale TOFU pin "
        f"foo→ATTACKER. Without this, the pin-race attack is permanent: "
        f"the operator can edit allowlist.json all they want and the legit "
        f"peer remains invisible. Got trust={trust!r}."
    )
