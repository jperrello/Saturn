# RUN_NOTES_MAY05 — autonomous promo-push handover

For the human re-entering the loop. Branch: `autonomous/promo-push`. Continues directly from MAY04. Pre-spec: `RUN_BRIEF_MAY05.md`. Live document — final commit list, test counts, and crew tally are filled at land-the-plane.

## What shipped so far — one paragraph

Two parallel buckets under athena dispatch, ~10 commits since fork from MAY04 tip `50750fe`. **Bucket A (polish)** lifted the `saturn_meta` receipt envelope to the remaining chat surfaces (cbt.1) and hardened chat UX with regression guards plus three Bombadil/playwright proofs (cbt.2.a long-stream, cbt.2.b attachments, cbt.2.c MCP-unreachable human-readable error). **Bucket B (new features)** delivered full client-side failover against the locked falsifiable spec (cbt.4 — five bullets, <2s switch, sticky, per-model affinity, `saturn_meta.routing.events` integration) and four discovery improvements (cbt.3.a settle-time plumb, cbt.3.b persistent worker pool for userspace resolves, cbt.3.c cross-process flock on `known_nodes`, cbt.3.d `last_seen` + `max_age` zombie filter). The mDNS-edge subbeads (cbt.5–8) are entering land with cbt.8 TXT-validator already in. Geoff produced `DISCOVERY_AUDIT.md` and `PRE_SPECS_B3.md §17.G.{1-4}` ahead of the contracts; brutus pinned 9 contracts; forge spawned a new `bombadil` crew member to own the UI lane.

## Continuity from MAY04

MAY04 landed at `50750fe`. This run inherits its eight-group `AdminConfig` schema, boot validators, bearer-token auth, TOFU `node_id` pinning, beacon sleep-transition + power-mgmt opt-in, and the `saturn_meta` receipt envelope on `/api/chat`. Two MAY04-deferred items become entry edges of this run: `qj5.15.2` (lifted into `Saturn-cbt.1`) and `qj5.16.13.3` (TOFU confirmation gate).

All workers `clear-and-talk` between bucket pivots; MAY04 per-worker context bloat does not bleed in.

## Run scope

Two buckets, dispatched in parallel. Router: athena. Hard cap: 8 hours. User out of the loop.

1. **Bucket A — promo-push polish.**
   - **A.1 — Saturn-cbt.1.** Lift `saturn_meta` receipt envelope from `/api/chat` to the other three chat surfaces per `PRE_SPECS_B3.md` §17.F.
   - **A.2 — Saturn-cbt.2.** Bombadil + playwright extended chat-UX coverage: long messages, attachments via `+` menu, MCP edges, edit-and-regenerate flake.
2. **Bucket B — new feature work.**
   - **B.1 — Saturn-cbt.3.** Discovery improvements: settle tuning, parallel resolves, identity-churn under TOFU + allowlist, cache-TTL hygiene.
   - **B.2 — Saturn-cbt.4.** Client-side failover (full spec). Falsifiable success: `/v1/health` 2x-fail or active 5xx triggers <2s switch, sticky to new service, per-model affinity, receipt integration via `saturn_meta.routing.events`.
   - **B.3 — Saturn-cbt.5–8.** mDNS edge cases: AP isolation, multi-interface, IPv6/dual-stack, large TXT records.

## What shipped — by bucket

### Bucket A — polish

- `347bdc9` **cbt.1** — `saturn_meta` receipt envelope lifted to `/api/proxy/chat` (saturn/web.py:848-885) and runner `/v1/chat/completions`. §17.F surfaces 1–3 covered; surface 4 (Brutus bridge) inventoried.
- **cbt.2.a** — regression-guard for the chat-UX baseline. Locks the post-MAY04 chat surface so cbt.2.b/c hardening cannot silently regress qj5.1–qj5.6.
- **cbt.2.a.ui — Saturn-3t8** — Bombadil/playwright long-stream proof. UI does not freeze on >4k / >32k token completions; receipt still lands.
- **cbt.2.b — Saturn-6g1** — Bombadil/playwright attachments coverage via the `+` menu: file types, size limits, error states.
- `5ac0a28` **cbt.2.c — Saturn-c4n** — MCP unreachable handler unwraps `BaseExceptionGroup` so the user-facing error is human-readable instead of a Python traceback header.

### Bucket B — new features

- `4f05fdb` **cbt.4 — Saturn-cbt.4** — Full client-side failover on `/api/system/chat`. All five bullets of the locked falsifiable spec: 2x-fail health gate, 5xx-on-active-request switch, <2s end-to-end switch latency, sticky session post-switch, per-model affinity (no silent wrong-model retry), `saturn_meta.routing.events` receipt integration with `{from, to, reason, at}` per event.
- `75c58f9` **cbt.3.a — Saturn-o6a** — Discovery `settle_time` arg now plumbs through to `SettleDetector` (it was being dropped at the boundary).
- `2c9ef90` **cbt.3.b — Saturn-nu4** — Parallel resolves via a **persistent worker pool** in the userspace backend. Lesson recorded: spinning a fresh `ThreadPoolExecutor` per `discover()` call wins on micro-bench but loses under churn (TCB cost dominates on burst-of-N rapid scans). Persistent pool wins both.
- `8d2bbfd` **cbt.3.c — Saturn-3to** — Cross-process `flock` around mutators on `known_nodes` JSON. Two Saturn instances on the same host can no longer race-corrupt the trust file.
- `fa57189` **cbt.3.d — Saturn-6m1** — `SaturnService.last_seen` field + `discover(max_age=...)` zombie filter. Stale entries (peer disappeared without goodbye) drop out of the result set instead of haunting the priority sort.

### Mid-run scaffolding (pre-contract)

- **DISCOVERY_AUDIT.md** (geoff) — pre-contract audit for B.1; surfaced the four cbt.3 sub-beads and identified the persistent-pool lesson before brutus contracts landed.
- **PRE_SPECS_B3.md §17.G.{1,2,3,4}** (geoff) — field-level pre-specs for each B.3 mDNS edge: §17.G.1 AP isolation, §17.G.2 multi-interface, §17.G.3 IPv6/dual-stack, §17.G.4 large TXT records.
- **9 brutus contracts pinned** across cbt.2.{a,b,c}, cbt.3.{a,b,c,d}, cbt.4, cbt.8 — falsifiable acceptance per bead before hardener implementation.
- `0423450` demo — failover probe + AP-isolation repro stub (cbt.4 + cbt.5).
- `cb8d525` demo — post-ship captures for cbt.1, cbt.2.a, cbt.2.c, cbt.4 + `LANDING_DEMO.md` §8.

### Carry-over fixes

- `500f576` **qj5.16.13.3** — TOFU pin deferred until ≥2 confirmations. Closes the MAY04-deferred edge where a single rogue advertisement could pin trust.

### B.3 mDNS edges — partial

- `173ad9e` **cbt.8 — §17.G.4** — TXT advertise-time validator. Hard-fails advertisement if TXT exceeds the documented safe ceiling (avoids fragmentation/silent drop).
- _cbt.5 (AP isolation), cbt.6 (multi-interface), cbt.7 (IPv6/dual-stack) — pending land._

## Crew

- New crew member **`bombadil`** spawned by forge to own the UI lane (Bucket A.2 hardening + landing-demo capture). Took ownership of cbt.2.a.ui (Saturn-3t8) and cbt.2.b (Saturn-6g1).

## Bead status

_Final tally at land-the-plane._

### Closed this run

- `Saturn-cbt.1` — `347bdc9`.
- `Saturn-c4n` (cbt.2.c MCP unreachable) — `5ac0a28`.
- `Saturn-o6a` (cbt.3.a settle plumb) — `75c58f9`.
- `Saturn-nu4` (cbt.3.b persistent worker pool) — `2c9ef90`.
- `Saturn-3to` (cbt.3.c cross-proc flock) — `8d2bbfd`.
- `Saturn-6m1` (cbt.3.d last_seen + max_age) — `fa57189`.
- `Saturn-cbt.4` (full failover) — `4f05fdb`.
- `Saturn-cbt.8` partial (§17.G.4 TXT validator) — `173ad9e`.
- `Saturn-qj5.16.13.3` — `500f576`.
- `Saturn-3t8` (cbt.2.a.ui long-stream proof) — bombadil capture, see `LANDING_DEMO.md` §8.
- `Saturn-6g1` (cbt.2.b attachments proof) — bombadil capture, see `LANDING_DEMO.md` §8.

### In-progress at draft time

- `Saturn-cbt.2`, `Saturn-cbt.3`, `Saturn-cbt.5`, `Saturn-cbt.6`, `Saturn-cbt.7`, `Saturn-cbt.8` — sub-bead work continuing.
- `Saturn-cbt` — epic, closes when all sub-beads close.

### Deferred follow-ups

_Filled at land-the-plane. MAY04 P2/P3 carry-overs (`qj5.13.8`, `qj5.13.10`, `qj5.14.2`, `qj5.14.3`, `qj5.15.1`, `qj5.16.13.5`, `qj5.13.5`, `qj5.13.9`, `qj5.14.4`, `qj5.15.3`, `qj5.16.13.4`, `qj5.16.15`) remain open unless explicitly cleared this run; new follow-ups land as `Saturn-cbt.*.<n>` sub-beads._

## Final commit list

_Filled at land-the-plane via `git log --oneline 50750fe..autonomous/promo-push`._

Tip-of-run: _TBD_

## Test counts

_Filled at land-the-plane. Sources: `tests/bombadil/run.sh`, `pytest -q`, playwright captures in `LANDING_DEMO.md`._

| Suite | Pre-run (`50750fe`) | Post-run | Δ |
|---|---|---|---|
| pytest | _TBD_ | _TBD_ | _TBD_ |
| bombadil | _TBD_ | _TBD_ | _TBD_ |
| playwright | _TBD_ | _TBD_ | _TBD_ |

## Crew tally

_Filled at land-the-plane via `git shortlog -sn 50750fe..autonomous/promo-push` cross-referenced with `crew list`. New `bombadil` member (UI lane) is expected to dominate the cbt.2.* commit count._

## Architectural notes worth carrying forward

- **Persistent worker pool > per-call pool** for userspace mDNS resolves. Recorded in cbt.3.b (`2c9ef90`). Per-call pools win on micro-bench, lose under churn — thread-creation-block dominates on rapid bursts of `discover()` calls. Apply broadly: any I/O-bound parallelism inside a hot loop should use a long-lived pool.
- **Cross-process flock around `known_nodes` mutators** (cbt.3.c, `8d2bbfd`). Two Saturn instances per host is supported (priority routing assumes it). The trust file is shared state and needs OS-level locking, not just an in-process `threading.Lock`.
- **`last_seen` + `max_age` zombie filter** (cbt.3.d, `fa57189`) is the corollary of "mDNS goodbyes are best-effort." Treat unreachability as the source of truth, not the goodbye packet.
- **Failover receipt integration** (cbt.4). Routing decisions land in the same `saturn_meta` envelope as config provenance: one structured receipt per turn, not separate observability surfaces. Pattern: `saturn_meta.routing.events: [{from, to, reason, at}]`.

## Pointer index

| File | Purpose |
|---|---|
| `RUN_BRIEF_MAY05.md` | This run's pre-spec. Two buckets, dispatch order, success criteria. |
| `RUN_NOTES_MAY04.md` | Prior-run handover. Architectural decisions and deferred bead map. |
| `PRE_SPECS_B3.md` | §17.F receipt-lift contract; §17.G.{1–4} mDNS-edge pre-specs added this run. |
| `DISCOVERY_AUDIT.md` | _New this run_ — geoff's pre-contract audit for cbt.3. |
| `LANDING_DEMO.md` | Demo index. §8 holds cbt.* captures. |
| `FINAL_VERDICT.md` | brutus's MAY04 verdict. Refreshed at land if invariants change. |
| `CONFIG_RECEIPT_PATTERNS.md` | qj5.15 patterns; cbt.1 surface lifts conform. |
| `SECURITY_AUDIT.md` | Audit chain. cbt.* mDNS hardening extends §15/§16. |
| `BONJOUR_AVAHI_FACTS.md` | gullivan research; sourced for B.3 mDNS edges. |
| `docs/admin/discovery.md` | _New this run_ — admin-actionable discovery doc (lands with cbt.3). |
| `docs/admin/failover.md` | _New this run_ — failover behavior + receipt (lands with cbt.4). |
| `docs/admin/network-troubleshooting.md` | _New this run_ — AP isolation, multi-NIC, IPv6, TXT limits (lands with cbt.5–8). |

## Suggested re-entry prompt

_Filled at land-the-plane._
