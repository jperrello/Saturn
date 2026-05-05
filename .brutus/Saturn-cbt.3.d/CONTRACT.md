# CONTRACT — Saturn-cbt.3.d: `last_seen` field + `discover(max_age=…)` filter

**Status:** RED. 2 tests pinned.
**Implementer:** athena will route (recommended: hardener — small dataclass + small filter).

## Spec restatement (falsifiable)

Two missing pieces blocking caller-driven zombie eviction:

1. **`SaturnService.last_seen: float`** — unix seconds. MUST be populated to
   `time.time()` on every backend add / update event. Stale entries (no
   re-advertisement) keep their old `last_seen`.

2. **`discover(timeout, settle_time, max_age=...)`** — when `max_age` is
   provided, the result list MUST exclude any service whose
   `time.time() - last_seen > max_age`. `max_age=None` (default) keeps the
   current behavior unchanged.

## Test files

- `saturn/tests/test_discovery_max_age_cbt3d.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_discovery_max_age_cbt3d.py --no-header -rN --tb=short
```

No external dependency — Zeroconf on loopback.

## Captured red output

```
saturn/tests/test_discovery_max_age_cbt3d.py:86: AssertionError: SaturnService
  must carry a `last_seen` field (unix seconds float). Currently no such
  attribute. Add it to the dataclass at saturn/discovery.py:75-95 and populate
  it on each add/update event.

saturn/tests/test_discovery_max_age_cbt3d.py:106: TypeError: discover() got an
  unexpected keyword argument 'max_age'
========================= 2 failed, 1 warning in 5.07s =========================
```

Full transcript: `.brutus/Saturn-cbt.3.d/transcript.md`.

## Oracle definition

| Field | Oracle |
|---|---|
| `s.last_seen` exists | `hasattr(s, "last_seen")` |
| `s.last_seen` is positive number | `isinstance(ls, (int, float)) and ls > 0` |
| `s.last_seen` close to `discover()` return | `returned_at - 30 <= ls <= returned_at + 1` |
| `discover(max_age=0.0)` filters everything | service NOT in result |
| `discover(max_age=600.0)` keeps fresh | service IS in result |

## Out of scope

- Active liveness probe / `/v1/health` sweep (cross-cuts cbt.4). File as
  **cbt.3.d.sweep** if/when needed; coordinate with cbt.4 owner so the
  health-check loop is shared.
- Persisting `last_seen` across `SaturnDiscovery` restarts.
- TXT record-driven re-validation.
- Any other audit area (a/b/c are separate brutus contracts).

## Implementer

athena will route. Suggested: **hardener**. ETA: ~10 min.

## Transcript

`.brutus/Saturn-cbt.3.d/transcript.md`
