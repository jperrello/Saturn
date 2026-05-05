# VERDICT — Saturn-cbt.5

**Status:** GREEN.
**Implementer:** hardener.

```
saturn/tests/test_isolation_cbt5.py — 2 passed
```

`saturn/mdns/isolation.py` exists with `IsolationProbe` dataclass (6 fields)
and `probe(timeout=4.0)`. Loopback round-trip reports `self_seen=True`,
`suspected_ap_isolation=False`. Oracle satisfied.

Adversarial states (real AP isolation, no-link) and `/api/discover`
integration remain in **cbt.5.adversarial** / **cbt.5.web** sub-beads.

Transcript: `.brutus/Saturn-cbt.5/transcript.md`.
