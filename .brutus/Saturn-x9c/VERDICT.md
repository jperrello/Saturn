# VERDICT — Saturn-x9c / cbt.7.advertise.v6filter

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `56ee730`.

```
saturn/tests/test_v6_filter_gaps_x9c.py — 1 passed
```

`saturn/mdns/interfaces.py:routable_addrs(family="v6")` now excludes
ULA (`fc00::/7`, `fd00::/7`), 6to4 (`2002::/16`), Teredo (`2001::/32`),
and mixed-case `fe80:` link-local. Legitimate global address
(`2607:f8b0:4005:809::200e`) is retained. Geoff's audit finding closed.

Transcript: `.brutus/Saturn-x9c/transcript.md`.
