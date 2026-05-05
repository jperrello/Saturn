# cbt.3.d — `SaturnService.last_seen` + `discover(max_age=…)` zombie filter

**Bead:** Saturn-6m1   **Commit:** `fa57189`

Adds the data and the kwarg required to drop "zombie" services from
`discover()` results — services that announced once but stopped
multicasting hours ago and are no longer reachable.

- `SaturnService` gains `last_seen: float` (unix seconds).
- Populated from `time.time()` in `SaturnDiscovery._add()` on every
  add/update event.
- `discover(max_age=None)` kwarg: when set to a number of seconds,
  filter out services whose `last_seen` is older than `now - max_age`.
- Default `max_age=None` preserves prior behaviour exactly.

Active `/v1/health` sweep is explicitly out of scope (cross-cuts
cbt.4 / failover) and tracks under `cbt.3.d.sweep`.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_discovery_max_age_cbt3d.py
```

## Captured output

```text
saturn/tests/test_discovery_max_age_cbt3d.py::test_saturnservice_carries_last_seen_timestamp PASSED
saturn/tests/test_discovery_max_age_cbt3d.py::test_discover_max_age_kwarg_filters_old_entries PASSED
========================= 2 passed in <Ns> ============================
```

## Why this matters

Without `max_age`, the Network Scan tab keeps surfacing peers that left
the LAN hours ago. With it, callers can ask for "only services I've
heard from in the last 5 minutes" and get a clean list — the smallest
piece of liveness without the operational cost of an active health
sweep.
