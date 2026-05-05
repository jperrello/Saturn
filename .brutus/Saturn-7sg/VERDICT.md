# VERDICT — Saturn-7sg / cbt.7.dedup

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `189a86d`.

```
saturn/tests/test_dual_stack_dedup_cbt7_dedup.py — 1 passed
```

`SaturnDiscovery._add()` merges `addresses` across events for the same
`(node_id, name)`. Two events (v4 then v6) collapse into one stored
`SaturnService` whose `addresses` carries both `192.168.1.10` and
`fe80::1`. No overwrite.

Transcript: `.brutus/Saturn-7sg/transcript.md`.
