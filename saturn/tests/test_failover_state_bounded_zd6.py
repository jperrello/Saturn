"""Saturn-zd6 — bounded _failover_state to close DoS via X-Saturn-Conversation-Id spray.

P1 finding from geoff's security audit: `saturn/web.py:149` is a plain
unbounded dict mapping `conversation_id → peer_name`. An attacker spraying
many unique `X-Saturn-Conversation-Id` values (up to one per turn) grows
the process's resident memory without bound.

Geoff scoped fix: OrderedDict + MAX_STICKY=10000 cap + 1h TTL per entry
(optional per-IP cap deferred).

Falsifiable oracles:

  1. **Size cap.** After 10001 unique-key assignments to
     `saturn.web._failover_state`, `len(...)` MUST be ≤ 10000.
  2. **TTL eviction.** With `saturn.web.STICKY_TTL_S` monkeypatched to 0.1,
     a key inserted at t=0 and read at t≥0.2 MUST behave as absent (either
     `key not in dict` OR `dict.get(key) is None`).

NO MOCKS. Direct in-process exercise of the data structure.
"""

import time

import pytest


pytestmark = pytest.mark.timeout(30)


def test_failover_state_caps_at_max_sticky():
    import saturn.web as W
    # Reset to a known empty state. Implementation may expose .clear() or
    # require reassignment — try both.
    if hasattr(W._failover_state, "clear"):
        W._failover_state.clear()
    assert hasattr(W, "MAX_STICKY"), (
        "saturn.web must expose `MAX_STICKY` as a module constant per "
        "geoff's audit fix scope; default 10000."
    )
    cap = W.MAX_STICKY
    assert cap >= 100, f"MAX_STICKY too small to be meaningful; got {cap}"

    for i in range(cap + 1):
        W._failover_state[f"convo-{i:06d}"] = "peer-a"

    n = len(W._failover_state)
    assert n <= cap, (
        f"_failover_state must self-bound to MAX_STICKY={cap} entries to close "
        f"the DoS vector (X-Saturn-Conversation-Id spray); after {cap+1} unique-key "
        f"inserts, size is {n}. Replace the plain dict at saturn/web.py:149 with "
        f"an OrderedDict-based bounded structure that evicts oldest on overflow."
    )


def test_failover_state_evicts_after_ttl(monkeypatch):
    import saturn.web as W
    assert hasattr(W, "STICKY_TTL_S"), (
        "saturn.web must expose `STICKY_TTL_S` as a module constant (seconds; "
        "default 3600) per geoff's audit fix scope."
    )
    monkeypatch.setattr(W, "STICKY_TTL_S", 0.1)

    if hasattr(W._failover_state, "clear"):
        W._failover_state.clear()

    W._failover_state["old-convo"] = "peer-a"
    time.sleep(0.25)

    # Touch the structure (TTL eviction may be triggered on read or on next
    # write; either is acceptable).
    W._failover_state["fresh-convo"] = "peer-b"

    is_absent = "old-convo" not in W._failover_state
    is_none = W._failover_state.get("old-convo") is None
    assert is_absent or is_none, (
        f"after STICKY_TTL_S=0.1 and a 0.25s sleep, 'old-convo' must be evicted "
        f"(either absent or returning None); got "
        f"contains={'old-convo' in W._failover_state}, value={W._failover_state.get('old-convo')!r}. "
        f"Implement TTL via timestamp-keyed entries or a periodic sweep."
    )
