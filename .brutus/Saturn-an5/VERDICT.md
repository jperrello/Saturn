# VERDICT — Saturn-an5 / cbt.3.d.sweep

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `c53760c`.

```
saturn/tests/test_discovery_sweep_cbt3d_sweep.py — 1 passed
```

`SaturnDiscovery.sweep_stale(max_age)` evicts entries older than
`max_age` seconds while preserving fresh ones. `old-svc` (added ~0.6s
prior) is dropped at `sweep_stale(max_age=0.4)`; `new-svc` survives.

Active `/v1/health` probe loop remains in **Saturn-an5.probe**
(cross-cuts cbt.4 health-loop; sweep + probe should share the same
timer when both land).

Transcript: `.brutus/Saturn-an5/transcript.md`.
