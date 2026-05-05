# CONTRACT — Saturn-7sg / cbt.7.dedup: dual-stack address merge in `SaturnDiscovery._add`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.

## Spec restatement (falsifiable)

`saturn/discovery.py:228` (`self.services[key] = service`) overwrites the
stored `SaturnService` whenever a new event arrives for the same `(node_id,
name)` key. When dual-stack resolution lands (Saturn-1xh / cbt.7.1), the
v4 and v6 of the same logical service may arrive as two separate events
(or a single resolve report with both addresses, depending on backend);
the merge must preserve previously-seen addresses.

Oracle: feeding two `_on_event(...)` calls for the same `(node_id, name)`
— first carrying `addresses=["192.168.1.10"]`, second carrying
`addresses=["fe80::1"]` — MUST result in a single stored `SaturnService`
whose `addresses` contains BOTH strings.

## Test files

- `saturn/tests/test_dual_stack_dedup_cbt7_dedup.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_dual_stack_dedup_cbt7_dedup.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 0.14s
v4 address from the first event must be retained after the second (updated)
event; got addresses=['fe80::1']
```

Transcript: `.brutus/Saturn-7sg/transcript.md`.

## Oracle

| Field | Oracle |
|---|---|
| Number of stored services with name `dedup-test` | exactly 1 |
| `s.addresses` after both events | contains both `"192.168.1.10"` and `"fe80::1"` |

## Fix sketch

In `SaturnDiscovery._add`, instead of `self.services[key] = service`:

```python
existing = self.services.get(key)
if existing is not None:
    # merge address-plural fields
    seen = set(existing.addresses)
    for a in service.addresses:
        if a not in seen:
            existing.addresses.append(a)
            seen.add(a)
    # update last_seen, host (keep old host as primary if v4-preferred)
    existing.last_seen = service.last_seen
    # ... other field merges as needed
else:
    self.services[key] = service
```

Implementer free to deviate; the oracle is what matters.

## Out of scope

- Dropping addresses on `removed` event (currently the whole entry is
  popped — fine).
- TTL-based pruning of stale addresses inside the merged list.
- Resolution-side AAAA extraction (**Saturn-1xh / cbt.7.resolve**) — without
  that, real-world addresses may be empty in production but the dedup
  logic is independently testable as pinned here.
- Conflict on v4 vs v6 reachability — that's a connect-time concern
  (cbt.4 + Saturn-76f / cbt.7.prefer).

## Implementer

athena → hardener. ETA ~10 min.
