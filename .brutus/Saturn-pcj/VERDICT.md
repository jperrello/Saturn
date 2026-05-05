# VERDICT — Saturn-pcj / cbt.6.userspace (= cbt.6.1)

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `78b0a64`.

```
saturn/tests/test_userspace_multi_addr_cbt6_userspace.py — 1 passed
```

`UserspaceBackend.advertise()` now sources `ServiceInfo.addresses` from
`routable_addrs()`. Two injected addresses (`192.168.50.10`,
`192.168.60.10`) survive round-trip into the registered ServiceInfo.
Geoff's PARITY_REVIEW cbt.6.1 wire-in is load-bearing.

Transcript: `.brutus/Saturn-pcj/transcript.md`.
