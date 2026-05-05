# cbt.4.sec.zd6 — bounded `_failover_state` with TTL + LRU cap

**Bead:** Saturn-zd6 (P1, geoff security audit)   **Commit:** `8c91f1f`
**Successor:** Saturn-68j (`7222aba`) closes the third leg of the same
finding — see [`cbt.4.sec.68j-per-ip-sticky.md`](cbt.4.sec.68j-per-ip-sticky.md).

cbt.4 sticky-session pinning was backed by a plain `dict`. P1 finding
from geoff's security audit: an attacker spraying many unique
`X-Saturn-Conversation-Id` headers grew RSS without bound — pin every
new value forever, no eviction, no TTL.

Fix: replace the dict with `_StickyMap(OrderedDict)`:

  - **LRU cap** — at `MAX_STICKY = 10000` entries, `popitem(last=False)`
    evicts the oldest on overflow. Memory is now bounded.
  - **Per-entry TTL** — entries carry `(timestamp, value)` pairs.
    `get` / `__contains__` / `__getitem__` check
    `time.time() - ts <= STICKY_TTL_S` (default 3600 s); reads past
    TTL behave as absent. The map self-heals over time even without
    eviction pressure.
  - **Expired-purge on insert** — `__setitem__` purges expired entries
    before inserting and re-checks the cap, so a slow trickle of
    inserts keeps the working set tight.

`MAX_STICKY` and `STICKY_TTL_S` are exposed as module constants and
read live, so tests can dial them down without restarting.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_failover_state_bounded_zd6.py
```

Two prongs:

  1. **bounded** — fan out `MAX_STICKY + N` unique conversation-ids,
     assert the map size stays at `MAX_STICKY` and the oldest IDs are
     gone.
  2. **TTL** — set `STICKY_TTL_S` low, write an entry, sleep past
     TTL, assert the read returns absent.

## Captured output

```text
saturn/tests/test_failover_state_bounded_zd6.py::... PASSED  (2 prongs)
========================= 2 passed, 1 warning in 12.21s ============================
```

## Lineage

  - **zd6** (this bead) — global cap + TTL halves of the finding.
  - **68j** (`7222aba`) — per-IP cap closes the eviction-DoS gap that
    remained: a single hostile IP could still burn all 10 000 slots
    and evict legit pins via global FIFO; 68j adds
    `MAX_STICKY_PER_IP = 100` so blast radius stays per-tenant.

Together: sticky-session works, memory is bounded, and one bad client
can't push the rest of the network out of cache.
