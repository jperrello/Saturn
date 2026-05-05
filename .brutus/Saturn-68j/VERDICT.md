# VERDICT — Saturn-68j / cbt.4.sec.zd6.per_ip (P3)

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `7222aba`.

```
saturn/tests/test_failover_state_per_ip_cap_68j.py — 2 passed
```

`MAX_STICKY_PER_IP` constant + `_set_sticky(convo_id, peer, ip)` helper
landed. With `MAX_STICKY_PER_IP=10`, 15 sprays from one IP leave ≤ 10
attributed to that IP; cross-IP isolation holds (IP2's 5 entries survive
IP1's 11-spray). The `_failover_state` DoS surface is now fully closed:
global cap (zd6), TTL (zd6), per-IP cap (68j).

Transcript: `.brutus/Saturn-68j/transcript.md`.
