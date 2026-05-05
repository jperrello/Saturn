# FINAL VERDICT — autonomous/promo-push (2026-05-05 run)

Brutus aggregate over the run's red→green chain. Commit-ordered.

## Headline

- **77/77** across every shipped MAY05 brutus contract suite in one
  batched re-run (110.19s wall). Verified post-Saturn-68j land.
- **30 falsifiable contracts** authored, 30 GREEN.
- **28 hardener implementation commits** + 2 regression-guard contracts
  needing no impl. All P1 + P2 security findings closed.
- Run wall: first hardener commit `347bdc9` at 2026-05-04 21:41 PDT;
  final commit `7222aba` at 2026-05-05 00:54 PDT. **~3h 13m of
  hardener-time**, well inside the 8h cap.

## Per-bead test counts (commit-ordered)

| # | Bead | Count | Implementer commit |
|---|------|-------|--------------------|
| 1 | Saturn-cbt.1 — qj5.15.2 receipt lift to /api/proxy/chat + runner /v1/chat/completions | 3/3 | `347bdc9` |
| 2 | Saturn-cbt.4 — client-side failover (timeout / sticky / affinity / receipt) | 4/4 | `4f05fdb` |
| 3 | Saturn-oqm (cbt.2.a) — long-message HTTP regression guard | 1/1 | regression-guard |
| 4 | Saturn-c4n (cbt.2.c.unreachable) — MCP unreachable error clarity | 1/1 | `5ac0a28` |
| 5 | Saturn-ex3 (cbt.2.c.timeout) — MCP per-call asyncio.wait_for | 1/1 | `83633d3` |
| 6 | Saturn-eic (cbt.2.c.large) — MCP oversized-payload guard | 1/1 | `4961da8` |
| 7 | Saturn-o6a (cbt.3.a) — settle_time plumbed | 1/1 | `75c58f9` |
| 8 | Saturn-nu4 (cbt.3.b) — userspace parallel resolves | 1/1 | `2c9ef90` |
| 9 | Saturn-3to (cbt.3.c) — known_nodes fcntl.flock | 1/1 | `8d2bbfd` |
| 10 | Saturn-6m1 (cbt.3.d) — last_seen + discover(max_age) | 2/2 | `fa57189` |
| 11 | Saturn-cbt.5 — AP-isolation probe module | 2/2 | `5c7410c` |
| 12 | Saturn-cbt.6 — routable_addrs() helper | 3/3 | `f99354d` |
| 13 | Saturn-cbt.7 — dual-stack address-plural schema | 3/3 | `d30e014` |
| 14 | Saturn-cbt.8 — TXT validator module | 3/3 | `173ad9e` |
| 15 | Saturn-76f (cbt.7.prefer) — connect_address + SATURN_PREFER_V6 | 3/3 | `3a2cc30` |
| 16 | Saturn-bfx (cbt.8.integrate) — advertiser TXT validate + mtrunc | 2/2 + 3/3 cbt.8 regression | `6df7367` |
| 17 | Saturn-pcj (cbt.6.userspace) — UserspaceBackend.advertise via routable_addrs | 1/1 | `78b0a64` |
| 18 | Saturn-5yh (cbt.5.1) — /api/discover returns {services, isolation} | 1/1 | `b6b184f` |
| 19 | Saturn-1xh (cbt.7.resolve) — userspace _resolve walks v4+v6 | 1/1 | `0ccab52` |
| 20 | Saturn-9rv (cbt.7.advertise) — advertise-side AAAA records | 2/2 | `e7b6adf` |
| 21 | Saturn-7sg (cbt.7.dedup) — _add() merges addresses across events | 1/1 | `189a86d` |
| 22 | Saturn-an5 (cbt.3.d.sweep) — SaturnDiscovery.sweep_stale | 1/1 | `c53760c` |
| 23 | Saturn-zor (cbt.4.sec.token + amend) — auth gate + messages cap | 4/4 | `b6ab724` + `5eac74a` |
| 24 | Saturn-b3o (cbt.4.sec.ratelimit + amend) — rate-limit + routing.events hash | 1/1 + 1/1 | `01808b9` |
| 25 | Saturn-ggn (cbt.cross-client) — /v1/* HTTP-stack parity | 1/1 | regression-guard |
| 26 | Saturn-vyy (cbt.cross-client.real) — protocol-level cross-client | 1/1 | regression-guard |
| 27 | Saturn-x9c (cbt.7.advertise.v6filter) — ULA/6to4/Teredo/mixed-case fe80 | 1/1 | `56ee730` |
| 28 | Saturn-zt2 (cbt.5.1.tunnel-leak) — VPN/tunnel iface filter | 1/1 | `0709ad6` |
| 29 | Saturn-zd6 — bounded _failover_state TTL + LRU (P1) | 2/2 | `8c91f1f` |
| 30 | Saturn-xqw — api_base TXT SSRF gate (P1) | 15/15 | `127f708` |
| 31 | Saturn-93w — TOFU pin-race operator allowlist (P1) | 3/3 | `5930a72` |
| 32 | Saturn-eon (cbt.4.sec.api_base) — sanitize ALL TXT values (P2) | 5/5 | `b19fb80` |
| 33 | Saturn-jfs (cbt.5.1.probe-dos) — /api/discover rate limit (P2) | 1/1 | `4330b4d` |
| 34 | Saturn-68j (zd6.per_ip) — per-IP cap on _failover_state (P3) | 2/2 | `7222aba` |

(34 rows because Saturn-zor and Saturn-b3o each shipped two-pass:
original contract + audit-fold amend. Counted as one bead each in the
30-contract total; counts in the table reflect both passes.)

## Aggregate

```
77 passed, 6 warnings in 110.19s (0:01:50)
```

Captured 2026-05-05 post-Saturn-68j. The six warnings are the
long-standing `asyncio_mode` PytestConfigWarning + a couple of
deprecation notices from the `mcp` SDK; not regressions.

## Geoff audits closed

| Audit | Findings | Disposition |
|---|---|---|
| `DISCOVERY_AUDIT.md` (cbt.3 a/b/c/d) | 4 | All shipped (Saturn-o6a / nu4 / 3to / 6m1) |
| `PARITY_REVIEW_MAY05.md` (cbt.5.1 / 6.1 / 7.1 / 7.2 / 8.1 wire-ins) | 5 | All shipped (Saturn-5yh / pcj / 1xh / 9rv / bfx) |
| `FAILOVER_SECURITY.md` rough pass | 1 P1 (zd6) + 3 inline P2/P3 | All folded (Saturn-zd6 + zor.amend + b3o.amend + x9c + zt2) |
| `FAILOVER_SECURITY.md` full pass | 2 P1 + 2 P2 + 1 P3 ack | All shipped (xqw / 93w / eon / jfs / 68j) |

## Discipline summary

- Every contract has `.brutus/<bead>/CONTRACT.md` with restated spec,
  oracle, run command, captured red, fix sketch, out-of-scope.
- Every contract has `.brutus/<bead>/transcript.md` (showboat red and
  green captures).
- Every green contract has `.brutus/<bead>/VERDICT.md` with implementer
  commit + 1-line attestation.
- 4 regression-guard contracts (Saturn-oqm / b3o-original /
  ggn / vyy) shipped under the house rule "preserve-behavior, no red
  phase, verify only."
- 2 contracts AMENDED post-ship to fold geoff audit findings (Saturn-zor
  for P3 messages cap; Saturn-b3o for P2 routing.events hashing). bd
  reopened, new RED tests added, then re-greened.
- 1 deliberate refusal to fabricate verdicts when the user signaled
  "queue cleared" but git showed no commits. Reported the discrepancy;
  hardener resumed.
- Patterns captured at `.brutus/CHEATSHEET.md` (15 sections).
- Index for archaeology at `.brutus/RUN_INDEX_MAY05.md`.

## Out-of-lane self-routes (Brutus did NOT attempt)

| Bead | Lane | Reason |
|---|---|---|
| Saturn-3t8 (cbt.2.a.ui) | bombadil | UI-freeze proof needs Playwright |
| Saturn-6g1 (cbt.2.b attachments) | bombadil | UI-only (Web-UI/app.js:2409-2447) |
| Saturn-ao6 (cbt.2.d edit-regen) | bombadil → 9ha | UI-only; bombadil shipped `dcf235b`+`f868d50` |
| Saturn-cbt.5.adversarial | deferred | needs network harness (`pfctl`, AP-isolated hotspot) |
| Saturn-cbt.5.web | bombadil | Web-UI render of isolation diagnosis |
| Saturn-vyy.linux | deferred | needs avahi-browse environment |
| Saturn-ggn.go | deferred | needs Go test harness |

## Residual deferred sub-beads (filed by brutus' own contracts as out-of-scope follow-ups)

These were called out in CONTRACT.md "Out of scope" sections; bd ids may
or may not be filed depending on athena's queue:

- **Saturn-zd6.per_ip** — closed (became Saturn-68j).
- **Saturn-an5.probe** — active /v1/health probe loop (cross-cuts cbt.4).
- **Saturn-an5.timer** — periodic timer that calls sweep_stale automatically.
- **Saturn-1xh.bonjour / Saturn-1xh.avahi** — Bonjour and Avahi resolve
  AAAA extraction (separate platform paths).
- **Saturn-7.advertise.v6only** — IPv6-only advertise mode.
- **Saturn-7sg.ttl** — TTL-based pruning of stale addresses inside merged list.
- **Saturn-8.integrate.env** — SATURN_TXT_CEILING env override.
- **Saturn-5.adversarial** — real AP-isolation network states.
- **Saturn-5.1.ui** — Web-UI conditional render of AP-isolation diagnosis.
- **Saturn-jfs.cache** — 30s probe-result cache for /api/discover.
- **Saturn-zor.scopes** — RBAC beyond binary admin gate.
- **Saturn-xqw.allowlist** — operator-asserted api_base allowlist per peer.
- **Saturn-xqw.dns** — DNS-resolution-time re-validation of api_base host.
- **Saturn-93w.cluster** — cluster-wide allowlist sync.
- **Saturn-93w.learn** — auto-promotion of TOFU-pinned entries into allowlist.
- **Saturn-eon.encode** — Bonjour _encode_txt length-asserts.
- **Saturn-68j.ttl** — per-IP TTL distinct from global TTL.
- **Saturn-68j.allowlist** — high-volume legit IP allowlist (NAT scenarios).
- **Saturn-vyy.lan** — cross-host LAN browse harness.
- **Saturn-ggn.api** — Web-UI /api/* cross-client parity.
- **cbt.G.cfg** — CONFIG_FIELDS additions (advertise_all_interfaces / prefer_ipv6 / txt_safe_ceiling).

None blocking. Athena files when prioritized.

## What's in the air

- Hardener queue is empty post-Saturn-68j.
- All P1 + P2 + P3 security work shipped.
- Branch `autonomous/promo-push` is at `7222aba`.
- Brutus's contract surface is sealed for this run.

The plane is on the ground.
