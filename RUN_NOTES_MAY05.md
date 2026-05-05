# RUN_NOTES_MAY05 — autonomous promo-push handover

For the human re-entering the loop. Branch: `autonomous/promo-push`. Continues directly from MAY04. Pre-spec: `RUN_BRIEF_MAY05.md`. Tip at land: `c53760c` (cbt.3.d.sweep — `SaturnDiscovery.sweep_stale(max_age)`).

## What shipped this run — one paragraph

33 commits since fork from MAY04 tip `50750fe`. **Bucket A (polish)** lifted the `saturn_meta` receipt envelope to the remaining chat surfaces (cbt.1) and hardened chat UX with a regression guard plus four Bombadil/playwright proofs: long-stream (cbt.2.a / Saturn-3t8), attachments via `+` menu (cbt.2.b / Saturn-6g1), MCP unreachable / timeout / oversized payload (cbt.2.c / Saturn-c4n / Saturn-ex3 / Saturn-eic), and an edit-save orphan-DOM fix (Saturn-bny). **Bucket B (new features)** delivered full client-side failover against the locked falsifiable spec (cbt.4 — five bullets: <2s switch, 2x-fail health gate, sticky via `X-Saturn-Conversation-Id`, per-model affinity, `saturn_meta.routing.events` receipt) and a five-piece discovery refresh (cbt.3.a settle-plumb, cbt.3.b persistent worker pool, cbt.3.c cross-process flock on `known_nodes`, cbt.3.d `last_seen` + `max_age`, cbt.3.d.sweep `SaturnDiscovery.sweep_stale`). All four mDNS edges from §17.G shipped: AP-isolation probe (cbt.5) plus its `/api/discover` integration (cbt.5.1), multi-NIC `routable_addrs()` + userspace bind-all (cbt.6 + cbt.6.userspace), dual-stack v4+v6 across schema/advertise/resolve/prefer/dedup (cbt.7 + four sub-beads), and TXT advertise-time validation + prune + mtrunc + fail-loud (cbt.8 + cbt.8.integrate). Three new operator-grade docs (`docs/admin/discovery.md`, `failover.md`, `network-troubleshooting.md`) land in the same wave.

## Continuity from MAY04

MAY04 landed at `50750fe`. This run inherits its eight-group `AdminConfig` schema, boot validators, bearer-token auth, TOFU `node_id` pinning, beacon sleep-transition + power-mgmt opt-in, and the `saturn_meta` receipt envelope on `/api/chat`. Two MAY04-deferred items closed in this run as entry-edge work: `qj5.15.2` (lifted into `Saturn-cbt.1`) and `qj5.16.13.3` (TOFU confirmation gate, `500f576`).

All workers `clear-and-talk` between bucket pivots; MAY04 per-worker context bloat did not bleed in.

## Run scope

Two buckets, dispatched in parallel. Router: athena. Hard cap: 8 hours. User out of the loop.

1. **Bucket A — promo-push polish.** Saturn-cbt.1 (receipt lift) + Saturn-cbt.2 (chat-UX hardening: long messages, attachments, MCP edges, regen flake).
2. **Bucket B — new feature work.** Saturn-cbt.3 (discovery improvements), Saturn-cbt.4 (client-side failover full spec), Saturn-cbt.5–8 (four mDNS edges).

## What shipped — by bucket

### Bucket A — polish

- `347bdc9` **cbt.1** — `saturn_meta` lifted to `/api/proxy/chat` (`saturn/web.py:848-885`) and runner `/v1/chat/completions`. §17.F surfaces 1–3 covered.
- **cbt.2.a** — regression-guard for the chat-UX baseline against the qj5.1–qj5.6 surface; HTTP-layer proof for >4k-token messages (200 SSE, TTFB <5s, receipt with `prompt_tokens ≥ 1000`). UI-freeze proof tracks separately as cbt.2.a.ui below.
- **cbt.2.a.ui — Saturn-3t8** — Bombadil/playwright long-stream proof: 70s turn, `ttfb=2.94s`, `timer.p99=7.3ms`, monotonic bubble + scroll, send button recovers, zero console errors.
- **cbt.2.b — Saturn-6g1** — Bombadil/playwright `+`-menu attachments coverage: allowed/disallowed types, exact 100 KB boundary, `+` → attach hides menu, badge → remove clears input. All 7 oracle bullets green.
- `5ac0a28` **cbt.2.c — Saturn-c4n** — `MCPClientManager.call()` unwraps `BaseExceptionGroup` so unreachable MCP server reads `MCP server '<name>' unreachable at <url>: <inner>` instead of an anyio TaskGroup blob.
- `83633d3` **cbt.2.c.timeout — Saturn-ex3** — Per-call `asyncio.wait_for(..., CALL_DEADLINE_S)` around MCP invoke. Hung tools abort in <10s instead of inheriting the 300s `sse_read_timeout`.
- `4961da8` **cbt.2.c.large — Saturn-eic** — Hard-reject MCP tool payloads `> LARGE_RESULT_BYTES = 1 MiB`. Same shaped error as unreachable/timeout; chat-context budget preserved.
- `417ba93` **cbt.bny — Saturn-bny** — One-line `userDiv.remove()` in the Web-UI save handler kills the orphan-DOM bug after Save-and-regenerate. Bombadil `edit_ao6` re-attestation: A/B/C/E green; D's flip-to-FAIL filed as `Saturn-9ha` (mid-stream edit-save drift, P2).

### Bucket B — new features

#### B.1 — discovery improvements (cbt.3)

- `75c58f9` **cbt.3.a — Saturn-o6a** — `discover()` now passes `settle_time` into `SettleDetector(...)` instead of dropping it on the floor. Real Zeroconf, no mocks; wall-clock tracks two distinct settings.
- `2c9ef90` **cbt.3.b — Saturn-nu4** — Resolves moved off the zeroconf engine thread onto a `queue.Queue` + 8 persistent workers with per-`(action, name)` in-flight dedupe. Lesson recorded: per-call `ThreadPoolExecutor` wins on micro-bench, loses under churn (TCB cost dominates).
- `8d2bbfd` **cbt.3.c — Saturn-3to** — `fcntl.flock(LOCK_EX)` on a sibling `.lock` file wraps every `known_nodes` mutator. Real-subprocess fan-out test; closes the lost-write race that broke the qj5.7j3 + qj5.16.13 trust anchor.
- `fa57189` **cbt.3.d — Saturn-6m1** — `SaturnService.last_seen` populated on every add/update; `discover(max_age=…)` filters zombies. Default kwarg `None` preserves prior behaviour.
- `c53760c` **cbt.3.d.sweep — Saturn-an5** — `SaturnDiscovery.sweep_stale(max_age)` for long-lived browsers; fires the same `on_service_change("removed", svc)` callback as a real backend goodbye.

#### B.2 — client-side failover (cbt.4)

- `4f05fdb` **cbt.4 + cbt.4.0 — Saturn-cbt.4** — Failover on `/api/system/chat` (`saturn/web.py:1059-1218`). All five spec bullets green: active-5xx switch <2s, 2x-fail health gate, sticky via `X-Saturn-Conversation-Id` (with 30s anonymous hysteresis fallback), per-model affinity 502, `saturn_meta.routing.events: [{from, to, reason, at}]` receipt. Brutus 4/4 against two real FastAPI subprocess peers — no mocks.

#### B.3 — mDNS edge cases (cbt.5–8)

- `5c7410c` **cbt.5 — §17.G.1** — `saturn/mdns/isolation.py:probe(timeout=4.0)`. Loopback green; AP-isolation branch falsifiable via `UserspaceBackend.fault_filter`.
- `b6b184f` **cbt.5.1 — Saturn-5yh** — `/api/discover` response gains `isolation` key alongside `services`. Web-UI consumer (`Saturn-3d9 / cbt.5.1.ui`) is in-flight at land.
- `f99354d` **cbt.6 — §17.G.2** — `saturn/mdns/interfaces.py:routable_addrs()` (psutil-backed, IPv4-only at this stage). `psutil>=5.9.0` formalised in `pyproject`.
- `78b0a64` **cbt.6.userspace — Saturn-pcj** — `UserspaceBackend.advertise()` binds all addresses returned by `routable_addrs()`; clients on either subnet of a multi-NIC server see the same `node_id`.
- `d30e014` **cbt.7 — §17.G.3** — Schema lift: `ServiceRecord.addresses: List[str]` and `SaturnService.{addresses, ipv6}`; `host` retained as back-compat primary.
- `e7b6adf` **cbt.7.advertise — Saturn-9rv** — Advertise-side dual-stack: A and AAAA addresses both published.
- `0ccab52` **cbt.7.resolve — Saturn-1xh** — Userspace `_resolve()` walks both v4 and v6 address records.
- `3a2cc30` **cbt.7.prefer — Saturn-76f** — `connect_address(service)` (`saturn/discovery.py:311`) + `SATURN_PREFER_V6` env knob; v6→v4 fallback on connect timeout.
- `189a86d` **cbt.7.dedup — Saturn-7sg** — Discovery merges `addresses` across events for the same `node_id:name` key; same service is no longer listed twice across v4/v6 backends.
- `173ad9e` **cbt.8 — §17.G.4** — `saturn/mdns/txt.py`: `TXT_SAFE_CEILING=1200`, `TxtTooLarge`, `validate(props) -> int`. Per-entry >255B and total >ceiling both raise.
- `6df7367` **cbt.8.integrate — Saturn-bfx** — `SaturnAdvertiser.register()` validates before delegating; on `TxtTooLarge`, prune order is `models` → `capabilities` → `features`, set `mtrunc=1`. If still over after pruning, register fails loudly.

#### Carry-over fixes

- `500f576` **qj5.16.13.3** — TOFU pin deferred until ≥2 confirmations. Closes the MAY04-deferred edge where a single rogue advertisement could pin trust.

#### Mid-run scaffolding

- **DISCOVERY_AUDIT.md** (geoff) — pre-contract audit for B.1; surfaced cbt.3.{a,b,c,d} and the persistent-pool lesson before brutus contracts landed.
- **PRE_SPECS_B3.md §17.G.{1,2,3,4}** (geoff) — field-level pre-specs for each B.3 mDNS edge.
- **9+ brutus contracts pinned** across cbt.2.{a,b,c,c.timeout,c.large}, cbt.3.{a,b,c,d}, cbt.4, cbt.5, cbt.6, cbt.7, cbt.8 — falsifiable acceptance per bead before hardener implementation.
- `0423450` failover probe + AP-isolation repro stub.
- `cb8d525` / `6ac80be` / `e15f599` / `2138ce4` — post-ship demo capture sweeps; `LANDING_DEMO.md` §8 holds 15+ cbt.* rows.
- `08a840a` `docs/admin/{discovery,failover,network-troubleshooting}.md` — operator-grade runbooks landed by writer in the same wave.

## Crew

- New crew member **`bombadil`** spawned by forge to own the UI lane. Took cbt.2.a.ui (Saturn-3t8) and cbt.2.b (Saturn-6g1); follow-up edit-save re-attestation on cbt.bny.
- Crew tally: per-pane shortlog is collapsed into one author on the public branch; per-crew attribution lives in `.brutus/<bead>/transcript.md` and `crew list`.

## Bead status

### Closed this run

Bucket A: `Saturn-cbt.1`, `Saturn-c4n` (cbt.2.c), `Saturn-ex3` (cbt.2.c.timeout), `Saturn-eic` (cbt.2.c.large), `Saturn-bny` (cbt.bny), `Saturn-3t8` (cbt.2.a.ui), `Saturn-6g1` (cbt.2.b).

Bucket B.1: `Saturn-o6a` (cbt.3.a), `Saturn-nu4` (cbt.3.b), `Saturn-3to` (cbt.3.c), `Saturn-6m1` (cbt.3.d), `Saturn-an5` (cbt.3.d.sweep).

Bucket B.2: `Saturn-cbt.4`.

Bucket B.3: `Saturn-cbt.5`, `Saturn-5yh` (cbt.5.1), `Saturn-cbt.6`, `Saturn-pcj` (cbt.6.userspace), `Saturn-cbt.7`, `Saturn-9rv` (cbt.7.advertise), `Saturn-1xh` (cbt.7.resolve), `Saturn-76f` (cbt.7.prefer), `Saturn-7sg` (cbt.7.dedup), `Saturn-cbt.8`, `Saturn-bfx` (cbt.8.integrate).

Carry-over: `Saturn-qj5.16.13.3`.

### In-progress at land

- `Saturn-3d9` — cbt.5.1.ui Web-UI consume new `/api/discover {services, isolation}` shape.
- `Saturn-9ha` — cbt.2.d-D mid-stream edit-save drift (DOM=0 stored=1 after late stream completes).

### Open follow-ups filed this run

- `Saturn-cbt.2` — bucket epic; closes after 9ha lands.
- `Saturn-cbt` — run epic; closes when all sub-beads close.
- `Saturn-oqh` — cbt.G.cfg config plumbing for new mDNS modules (centralise `SATURN_ADVERTISE_ALL`, `SATURN_PREFER_V6`, `SATURN_TXT_CEILING`).
- `Saturn-b3o` — cbt.4.sec.ratelimit `/api/system/chat` rate limiting.
- `Saturn-zor` — cbt.4.sec.token `/api/system/chat` token validation.
- `Saturn-b5a` — cbt.5.web AP-isolation Web-UI integration (the SPA branch of the new `/api/discover` shape).
- `Saturn-5ir` — cbt.5.adversarial real AP-isolation network cases.
- `Saturn-v60` — `demo/_capture_cbt_4.py` vs test fixture single-source-of-truth.
- `Saturn-3bq` — `tests/bombadil/run.sh` missing `SATURN_ADMIN_PASSWORD` env.
- `Saturn-b46` — populate mDNS TXT records with models for custom module servers.

### MAY04 carry-overs (still open, not blocking)

`qj5.13.{1,2,3,5,8,9,10}`, `qj5.14.{2,3,4}`, `qj5.15.{1,3}`, `qj5.16.{12,13.4,13.5,15}`. Triage map in `RUN_NOTES_MAY04.md` §Remaining open.

## Final commit list

`git log --oneline 50750fe..autonomous/promo-push` → 33 commits. Tip: `c53760c`.

The full ordered list (newest first) is reproduced in commit order across the **What shipped** sections above. Notable demo waves: `cb8d525`, `6ac80be`, `e15f599`, `2138ce4`. Notable docs: `08a840a` (admin/{discovery, failover, network-troubleshooting}), `0244ab9` (this file's first draft).

## Test counts

To be refreshed by brutus into a `FINAL_VERDICT_MAY05.md` if the run warrants. Spot checks at land:

- `saturn/tests/test_failover_cbt4.py` — 4/4 (cbt.4 brutus VERDICT, `4f05fdb`).
- `saturn/tests/test_isolation_cbt5.py` — green (cbt.5 brutus VERDICT, `5c7410c`).
- `saturn/tests/test_routable_addrs_cbt6.py` — green (cbt.6 brutus VERDICT, `f99354d`).
- `saturn/tests/test_dual_stack_cbt7.py` — green (cbt.7 brutus VERDICT, `d30e014` + sub-beads).
- `saturn/tests/test_txt_validate_cbt8.py` — green (cbt.8 brutus VERDICT, `173ad9e`).
- `saturn/tests/test_discovery_settle_cbt3a.py`, `test_discovery_max_age_cbt3d.py`, `test_known_nodes_cross_proc_cbt3c.py`, `test_userspace_parallel_resolve_cbt3b.py` — all green (cbt.3.* VERDICTs).
- `saturn/tests/test_mcp_edges_cbt2c.py`, `test_mcp_timeout_ex3.py`, `test_mcp_large_eic.py`, `test_long_messages_cbt2a.py` — green at land.
- Bombadil `chat` spec — bombadil/playwright captures recorded for cbt.2.{a.ui, b}, cbt.bny; see `LANDING_DEMO.md` §8.

## Architectural notes worth carrying forward

- **Persistent worker pool > per-call pool** for userspace mDNS resolves (cbt.3.b, `2c9ef90`). Per-call pools win on micro-bench, lose under churn — thread-creation-block dominates. Apply broadly: any I/O-bound parallelism inside a hot loop should use a long-lived pool.
- **Cross-process flock around `known_nodes` mutators** (cbt.3.c, `8d2bbfd`). Two Saturn instances per host is supported; the trust file is shared state and needs OS-level locking, not in-process `threading.Lock` alone.
- **`last_seen` + `max_age` zombie filter + `sweep_stale`** (cbt.3.d / cbt.3.d.sweep). Treat unreachability as the source of truth, not the goodbye packet. Long-lived browsers should `sweep_stale(max_age)` on a timer; one-shot callers pass `max_age` to `discover()`.
- **`address-plural` schema for v4/v6 dual-stack** (cbt.7). `host` stays back-compat as primary; `addresses: List[str]` carries every resolved record. Discovery dedup is keyed by `node_id:name`, not address — same node = same entry, regardless of how many addresses come back.
- **TXT validation at advertise time, not browse time** (cbt.8). Refusing to advertise an oversized TXT is correct — a fragmented multicast packet is silently dropped on most LANs, and "discovery works in dev, fails in prod" is harder to diagnose than a loud startup error.
- **Failover receipt integration** (cbt.4). Routing decisions land in the same `saturn_meta` envelope as config provenance: one structured receipt per turn, not separate observability surfaces. Pattern: `saturn_meta.routing.events: [{from, to, reason, at}]`.
- **`/api/discover` is additive** (cbt.5.1). Surfacing the AP-isolation probe through a new key on an existing endpoint preserves clients that don't know about it. Same pattern as `routing.events` extending `saturn_meta`.

## Pointer index

| File | Purpose |
|---|---|
| `RUN_BRIEF_MAY05.md` | This run's pre-spec. Two buckets, dispatch order, success criteria. |
| `RUN_NOTES_MAY04.md` | Prior-run handover. Architectural decisions and deferred bead map. |
| `PRE_SPECS_B3.md` | §17.F receipt-lift contract; §17.G.{1–4} mDNS-edge pre-specs added this run. |
| `DISCOVERY_AUDIT.md` | geoff's pre-contract audit for cbt.3 (settle, parallel resolves, identity churn, cache TTL). |
| `LANDING_DEMO.md` | Demo index. §8 holds the cbt.* captures (15+ rows at land). |
| `FINAL_VERDICT.md` | brutus's MAY04 aggregate verdict. A MAY05 refresh lands separately if brutus closes the per-bead chain into a single doc. |
| `FINAL_AUDIT_SUMMARY.md` | geoff's MAY04 audit-side recap. |
| `CONFIG_RECEIPT_PATTERNS.md` | qj5.15 patterns; cbt.1 surface lifts and `cbt.4` `routing.events` both conform. |
| `SECURITY_AUDIT.md` | Audit chain. cbt.* mDNS hardening extends §15/§16. |
| `BONJOUR_AVAHI_FACTS.md` | gullivan research; sourced for B.3 mDNS edges. |
| `docs/admin/discovery.md` | _New this run_ — operator runbook for discovery (settle, known_nodes, max_age, multi-NIC, AP-isolation, TXT). |
| `docs/admin/failover.md` | _New this run_ — operator runbook for `/api/system/chat` failover (breakers, sticky, hysteresis, `routing.events`). |
| `docs/admin/network-troubleshooting.md` | _New this run_ — first-pass probe + per-edge triage (AP isolation, multi-interface, IPv6, large TXT). |

## Suggested re-entry prompt

> Resume `autonomous/promo-push`. Branch tip: `c53760c`. MAY05 run is landed — Saturn-cbt.{1,4,5,6,7,8} closed plus cbt.3.{a,b,c,d,d.sweep} and cbt.2.{a, a.ui, b, c, c.timeout, c.large} + cbt.bny. Two beads still in_progress: `Saturn-3d9` (cbt.5.1.ui Web-UI consumer of `/api/discover {services, isolation}`) and `Saturn-9ha` (mid-stream edit-save drift after late stream completes — bombadil prong D failure). Open follow-ups filed this run: `Saturn-oqh` (config plumbing for new mDNS env knobs), `Saturn-b3o` / `Saturn-zor` (cbt.4 rate limit / token validation), `Saturn-b5a` / `Saturn-5ir` (cbt.5 Web-UI + adversarial). MAY04 P2/P3 carry-overs are still open and not blocking; map in `RUN_NOTES_MAY04.md`. Operator docs landed at `docs/admin/{discovery, failover, network-troubleshooting}.md` — wire them into `docs/index.md` if a Diátaxis pass is in scope. Start with `bd ready`.
