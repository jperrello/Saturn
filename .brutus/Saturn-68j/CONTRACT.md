# CONTRACT — Saturn-68j / cbt.4.sec.zd6.per_ip: per-IP cap on `_failover_state`

**Status:** RED. 1 test pinned (1 skipped pending the first).
**Implementer:** athena → hardener (P3; small follow-up to zd6).

## Spec restatement (falsifiable)

Saturn-zd6 closed the global-cap + TTL halves of the
`_failover_state` DoS finding. The remaining gap (geoff's optional
extension): a single attacker IP can still consume up to
`MAX_STICKY=10000` slots, evicting legitimate users' entries via the
FIFO ordering.

The fix MUST add per-IP attribution and an additional cap:

  - `saturn.web.MAX_STICKY_PER_IP: int` — module constant, default
    suggested 100 in production. Test uses a smaller value via
    monkeypatch.
  - `saturn.web._set_sticky(convo_id, peer, ip)` — the sanctioned write
    path. The existing call site at `saturn/web.py:1266` MUST be
    updated to call this helper with `_client_ip(request)`.
  - When an IP exceeds `MAX_STICKY_PER_IP`, oldest entries from THAT IP
    are evicted (not from other IPs).

## Test files

- `saturn/tests/test_failover_state_per_ip_cap_68j.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_failover_state_per_ip_cap_68j.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 skipped, 1 warning in 1.04s
saturn.web must expose `MAX_STICKY_PER_IP: int` as a module constant per
geoff's zd6 follow-up.
```

The second test is `pytest.skip`-gated on the first so the implementer
sees the missing-surface error first, fixes the surface, then sees the
behavioral test. Transcript: `.brutus/Saturn-68j/transcript.md`.

## Oracle definition

| Test | Setup | Oracle |
|---|---|---|
| `per_ip_cap_enforces` | `MAX_STICKY_PER_IP=10`, 15 sprays from one IP | `≤ 10` of those keys remain |
| `per_ip_cap_isolates_ips` | IP2 with 5 entries, then IP1 with 11 | IP2 retains all 5; IP1 retains ≤ 10 |

## Fix sketch (non-binding)

```python
# saturn/web.py
MAX_STICKY_PER_IP = 100

class _StickyMap(OrderedDict):
    # ...existing TTL + global cap logic...
    def __init__(self):
        super().__init__()
        self._by_ip: dict[str, list[str]] = {}

    def set_with_ip(self, key, value, ip):
        # Evict from this IP if over per-IP cap
        bucket = self._by_ip.setdefault(ip, [])
        cap = globals().get("MAX_STICKY_PER_IP", 100)
        while len(bucket) >= cap:
            old = bucket.pop(0)
            try: OrderedDict.__delitem__(self, old)
            except KeyError: pass
        # Then global cap + TTL via existing __setitem__
        self[key] = value
        bucket.append(key)


def _set_sticky(convo_id, peer, ip):
    _failover_state.set_with_ip(convo_id, peer, ip)


# Update saturn/web.py:1266:
# OLD:  _failover_state[convo_id] = c["name"]
# NEW:  _set_sticky(convo_id, c["name"], ip)
```

Implementer free to deviate. Note: when the global FIFO eviction in the
existing `__setitem__` removes an entry, the per-IP bucket's reference
becomes stale. The implementer should either (a) sweep stale references
on next `set_with_ip` from that IP, or (b) hook the global-eviction
path to also pop from the bucket. Either is fine; the oracle doesn't
require a specific approach.

## Out of scope

- Per-IP TTL (different from global TTL) — file as **Saturn-68j.ttl** if
  needed.
- Telemetry on per-IP eviction (count of evictions per IP per period).
- Allowlist of high-volume legit IPs (e.g., shared NAT). File as
  **Saturn-68j.allowlist** if production deployments hit the cap with
  legitimate traffic.

## Implementer

athena → hardener. P3. ETA ~15 min.

## Transcript

`.brutus/Saturn-68j/transcript.md`
