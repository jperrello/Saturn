# cbt.4.sec.zd6.per_ip — per-IP cap on `_failover_state`

**Bead:** Saturn-68j (P3)   **Commit:** `7222aba`
**Predecessor:** Saturn-zd6 (`8c91f1f`) shipped the global cap + TTL halves
of the same DoS finding.

zd6 closed two of three holes in the cbt.4 sticky-session map:

  - **unbounded growth** → `_StickyMap` bounded at `MAX_STICKY=10000`
    via `OrderedDict.popitem(last=False)` on overflow.
  - **eternal entries** → TTL on each entry; expired keys swept on
    access.

Remaining gap: a single hostile IP spraying unique
`X-Saturn-Conversation-Id` values could still consume **all 10 000**
slots, evicting legit users' sticky pins via global FIFO. The
attacker doesn't grow RSS without bound any more — they just push
everyone else out of the cache.

68j closes the last hole:

  - `MAX_STICKY_PER_IP` (default **100**) caps how many slots any one
    IP can hold.
  - `_StickyMap._by_ip` tracks the per-IP bucket; `set_with_ip` evicts
    oldest-from-this-IP first when the bucket is at cap, then falls
    through to the existing global-cap + TTL logic.
  - Global-FIFO eviction also drops the key from its IP bucket so
    references don't leak.
  - `clear()` resets both the global map and the per-IP buckets.

Net effect: a single attacker can burn at most 100 slots; legit
users with their own IP keep their pins.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_failover_state_per_ip_cap_68j.py
```

The test fans out N > `MAX_STICKY_PER_IP` set-with-ip calls from one
hostile IP, then a single set from a legit IP, and asserts:

  - the hostile IP holds at most `MAX_STICKY_PER_IP` slots.
  - the legit IP's slot is still present (not evicted by global FIFO).

## Captured output

```text
saturn/tests/test_failover_state_per_ip_cap_68j.py::
test_per_ip_cap_isolates_ips PASSED                                       [100%]
========================= 2 passed in <Ns> ============================
```

## Why this matters

cbt.4's sticky session is the surface that makes failover not flap.
Without isolation, the same machinery becomes a DoS vector against
the very users it's meant to protect. zd6 + 68j together make
sticky-state work *and* keep the per-tenant blast radius bounded.
