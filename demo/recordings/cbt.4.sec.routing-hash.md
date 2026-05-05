# cbt.4.sec / Saturn-b3o.amend — hash peer names in `saturn_meta.routing`

**Bead:** Saturn-b3o.amend (geoff P2)   **Commit:** `01808b9`

cbt.4 / cbt.4.0 made `saturn_meta.routing.{events, service}` part of
the receipt. That receipt is honest about what happened — and that
honesty is the problem when the receipt reader is hostile: literal
peer names let an admin-token holder (or stolen-creds attacker)
enumerate the entire peer mesh from a single chat turn.

Fix: `_alias_peer(name) -> sha256(name)[:8]`. Wired through:

  - `routing.events[*].from`
  - `routing.events[*].to`
  - `routing.service` (the chosen-service emission at line 1292)

8 hex chars (32 bits) is enough for an operator to correlate two
events on the same alias within a turn / log scope, and short enough
that the receipt stays human-readable. The mapping is **not**
persisted — same peer hashes consistently within a process but a
restart re-aliases (the operator with logs across both still
correlates via the underlying `node_id` recorded elsewhere; the
chat-receipt reader does not).

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_routing_events_hash_b3o.py
```

The test forces a failover and asserts that no event in
`saturn_meta.routing.events`, and `routing.service` itself, contains
any literal peer name from the discovered set; aliases are 8-char
hex.

## Captured output

```text
saturn/tests/test_routing_events_hash_b3o.py::
test_routing_events_do_not_leak_literal_peer_names PASSED                 [100%]
========================= 1 passed in <Ns> ============================
```

## Capture refresh

[`cbt.4-failover.md`](cbt.4-failover.md) shows the pre-amendment
receipt with literal `peer-a` / `peer-b`. Post-amendment that block
would read:

```json
{
  "routing": {
    "events": [{"from": "<8-hex>", "to": "<8-hex>",
                "reason": "active_5xx", "at": ...}],
    "service": "<8-hex>"
  },
  "schema_version": 1
}
```

The cbt.4 capture isn't regenerated — the routing *behaviour* is
unchanged; only the surface shape of the names. Future regenerations
of that capture (e.g. once Bonjour/Avahi resolve land) will pick up
the aliased shape automatically.
