# VERDICT — Saturn-93w / TOFU pin-race (P1)

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `5930a72`.

```
saturn/tests/test_tofu_pin_race_93w.py — 3 passed
```

`saturn.discovery.ALLOWLIST_PATH` exposed. Operator-asserted
`~/.saturn/allowlist.json` name → node_id map consulted before TOFU
promotion. With `{foo: LEGIT}` pre-seeded:

- `(foo, ATTACKER)` → `rebind_rejected`
- `(foo, LEGIT)` → `allowlist`
- `(foo, ATTACKER)` with stale `foo→ATTACKER` pin → still `rebind_rejected`
  (allowlist overrides stale pin)

Geoff's FAILOVER_SECURITY.md §(A) P1 closed. Pin-race attack vector closed
end-to-end: any host on the LAN can no longer permanently hijack a
service-name's identity by advertising first.

Transcript: `.brutus/Saturn-93w/transcript.md`.
