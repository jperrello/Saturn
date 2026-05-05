# CONTRACT — Saturn-an5 / cbt.3.d.sweep: in-memory `sweep_stale()` on `SaturnDiscovery`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.

## Spec restatement (falsifiable)

`SaturnDiscovery` MUST expose `sweep_stale(max_age: float) -> None` that
drops every entry from `self.services` whose `last_seen` is older than
`max_age` seconds.

This is the in-memory eviction half of DISCOVERY_AUDIT.md (d) note 2.
The companion network probe (`/v1/health` ping loop, cross-cutting
cbt.4 failover) is filed as **Saturn-an5.probe** — separate sub-bead.

## Test files

- `saturn/tests/test_discovery_sweep_cbt3d_sweep.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_discovery_sweep_cbt3d_sweep.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 0.78s
SaturnDiscovery must expose a `sweep_stale(max_age)` method that drops
entries whose last_seen is older than max_age.
```

Transcript: `.brutus/Saturn-an5/transcript.md`.

## Oracle

Test adds an "old" entry, sleeps 0.6s, adds a "new" entry, then calls
`sweep_stale(max_age=0.4)`:

| Field | Oracle |
|---|---|
| `"old-svc"` in remaining services | False (evicted; ~0.6s old > 0.4 max_age) |
| `"new-svc"` in remaining services | True (~0s old) |

## Fix sketch

```python
# saturn/discovery.py
def sweep_stale(self, max_age: float) -> None:
    cutoff = time.time() - max_age
    with self.lock:
        stale = [k for k, s in self.services.items()
                 if (s.last_seen or 0) < cutoff]
        for k in stale:
            removed = self.services.pop(k)
            if self.on_service_change:
                self.on_service_change("removed", removed)
```

Implementer free to deviate.

## Out of scope

- The actual periodic timer that calls `sweep_stale` automatically — file
  as **Saturn-an5.timer** if needed (different concern; needs threading
  decisions and shutdown semantics).
- `/v1/health` probing of remote peers — **Saturn-an5.probe** (cross-cuts
  cbt.4 health-loop; the loops should be shared, not duplicated).
- Eviction notification semantics beyond `on_service_change`.

## Implementer

athena → hardener. ETA ~10 min.
