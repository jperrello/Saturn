# VERDICT — Saturn-b3o / cbt.4.sec.ratelimit (+ amended P2)

**Status:** GREEN.
**Implementer:** hardener (amend); brutus (regression-guard for original).
**Implementation commit:** `01808b9` (peer-name hashing).

```
saturn/tests/test_system_chat_ratelimit_b3o.py    — 1 passed (regression guard)
saturn/tests/test_routing_events_hash_b3o.py      — 1 passed (P2 fold)
```

Original rate-limit invariant preserved: `SATURN_RATE_RPM=2` burst yields
≥3 of 6 requests at 429 with `Retry-After`.

Folded P2: `saturn_meta.routing.events[*].{from,to}` and `routing.service`
are now hashed via the new alias helper. After a forced failover off
`peer-a` → `peer-b`, the receipt no longer carries either literal name.
Geoff's audit P2 (peer-mesh enumeration via routing receipt) is closed.

Transcript: `.brutus/Saturn-b3o/transcript.md`.
