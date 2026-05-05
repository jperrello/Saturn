# VERDICT — Saturn-jfs / cbt.5.1.probe-dos (P2)

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `4330b4d`.

```
saturn/tests/test_api_discover_ratelimit_jfs.py — 1 passed
```

`/api/discover` now calls `_check_rate(ip)` at handler entry, matching
the rest of the rate-limited `/api/*` surface. Burst of 6 GETs at
`SATURN_RATE_RPM=2` yields ≥3 of 6 at HTTP 429 with `Retry-After`.

Geoff's FAILOVER_SECURITY.md §(C) P2 closed. The 9-second-blocking-probe
amplification vector (10 attacker requests → 90 process-seconds + 10
spurious mDNS announcements) is closed.

Optional follow-up `Saturn-jfs.cache` (30s probe-result cache) deferred —
file if the rate limit alone proves insufficient under sustained load.

Transcript: `.brutus/Saturn-jfs/transcript.md`.
