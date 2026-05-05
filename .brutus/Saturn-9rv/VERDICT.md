# VERDICT — Saturn-9rv / cbt.7.advertise (= cbt.7.2)

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `e7b6adf`.

```
saturn/tests/test_dual_stack_advertise_cbt7_advertise.py — 2 passed
```

`routable_addrs(family=...)` accepts the kwarg (`v4` / `v6` / `both`).
`UserspaceBackend.advertise()` packs both 4-byte AF_INET and 16-byte
AF_INET6 entries into `ServiceInfo.addresses`. Both injected synthetic
addresses (`192.168.50.10` and `fe80::abcd:1`) round-trip into the
published record.

Transcript: `.brutus/Saturn-9rv/transcript.md`.
