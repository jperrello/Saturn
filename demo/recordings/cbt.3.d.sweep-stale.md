# cbt.3.d.sweep — `SaturnDiscovery.sweep_stale(max_age)`

**Bead:** Saturn-an5   **Commit:** `c53760c`

In-memory eviction half of `DISCOVERY_AUDIT.md` (d). cbt.3.d
(`fa57189`) added the `last_seen` field and the `discover(max_age=…)`
filter on the *read* path; sweep is the matching *write* path.

`sweep_stale(max_age)` walks `self.services` under `self.lock`, pops
every entry whose `last_seen` is older than `now - max_age` seconds,
and returns the list of evicted `node_id`s for caller logging.

The `discover(max_age=…)` filter alone preserves zombies in memory
forever (it just hides them at read time). Sweep actually drops them
so memory doesn't grow without bound on long-running Saturn web
processes that have seen many transient peers.

Active `/v1/health`-driven sweep (separate from time-based eviction)
still tracks under `cbt.3.d.sweep.health`.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_discovery_sweep_cbt3d_sweep.py
```

The test seeds `_discovered` with one fresh and one synthetically-old
entry, calls `sweep_stale(max_age)`, asserts the old one was returned
in the eviction list and the fresh one survived.

## Captured output

```text
saturn/tests/test_discovery_sweep_cbt3d_sweep.py::
test_sweep_stale_drops_old_entries_keeps_fresh_ones PASSED                [100%]
========================= 1 passed in <Ns> ============================
```
