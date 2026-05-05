"""Saturn-b3o (folded P2 from geoff audit) — routing.events peer-name hashing.

Geoff's audit P2: `saturn_meta.routing.events` (saturn/web.py:1291-1292)
emits literal peer names (e.g., `"peer-a"`, `"peer-b"`) and switch
reasons. Even with the cbt.4.sec.token gate now in place, an admin-token
holder (or anyone with stolen creds) reading the receipt enumerates the
full peer mesh — useful intel for an attacker probing the network.

Falsifiable oracle: after a forced failover (peer-a returns 5xx →
peer-b serves), `saturn_meta.routing.events[*]` MUST NOT contain the
literal advertised peer names. They MUST be opaque tokens (hashes / hex
prefixes / etc) of bounded length. Likewise `saturn_meta.routing.service`
MUST be opaque.

NO MOCKS. Reuses the real-FastAPI-peer subprocess fixtures from
test_failover_cbt4.py.
"""

import json
import time

import pytest

# Reuse the real subprocess peer rig from cbt.4.
from .test_failover_cbt4 import (  # noqa: F401
    peers, app_client, _set_state, _last_meta, _post_chat,
)


pytestmark = pytest.mark.timeout(60)


def test_routing_events_do_not_leak_literal_peer_names(app_client):
    client, peers = app_client
    a, b = peers[0], peers[1]
    _set_state(a, chat_500=True)  # force a failover off peer-a onto peer-b

    convo = "b3o-routing-hash-convo"
    r = _post_chat(client, convo=convo)
    assert r.status_code == 200, f"setup: expected 200 after switch; got {r.status_code}: {r.text[:300]}"

    meta = _last_meta(r.text)
    routing = meta.get("routing") or {}
    events = routing.get("events") or []
    assert events, f"setup: routing.events should be non-empty after a forced switch; meta={meta!r}"

    leaked = []
    for ev in events:
        for k in ("from", "to"):
            v = ev.get(k)
            if v in ("peer-a", "peer-b"):
                leaked.append((k, v))
    svc = routing.get("service")
    if svc in ("peer-a", "peer-b"):
        leaked.append(("service", svc))

    assert not leaked, (
        f"saturn_meta.routing leaks literal peer names {leaked!r}; per geoff's "
        f"audit P2, peer names in the receipt must be hashed (e.g., "
        f"sha256(name)[:8]) so receipt readers cannot enumerate the peer mesh. "
        f"Fix: introduce `saturn.web._alias_peer(name) -> str` that returns a "
        f"deterministic hex prefix and wire it through the events accumulator "
        f"and at saturn/web.py:1291-1292."
    )

    # Also assert the alias values are bounded (a reasonable hash prefix is ≤ 16 chars).
    for ev in events:
        for k in ("from", "to"):
            v = ev.get(k) or ""
            assert isinstance(v, str) and 0 < len(v) <= 32, (
                f"routing event field {k}={v!r} must be a non-empty bounded string "
                f"(≤ 32 chars); got len={len(str(v))}"
            )
