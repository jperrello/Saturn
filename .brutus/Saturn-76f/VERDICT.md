# VERDICT — Saturn-76f / cbt.7.prefer

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `3a2cc30`.

```
saturn/tests/test_prefer_v6_cbt7_prefer.py — 3 passed
```

`saturn.discovery.connect_address(service)` returns the IPv4 by default;
returns IPv6 when `SATURN_PREFER_V6=1` and v6 is in `service.addresses`;
falls back to v4 when prefer-v6 is set but no v6 advertised.

Transcript: `.brutus/Saturn-76f/transcript.md`.
