# RUN_NOTES_MAY05 — autonomous promo-push handover

For the human re-entering the loop. Branch: `autonomous/promo-push`. Continues directly from MAY04. Pre-spec: `RUN_BRIEF_MAY05.md`. Tip at land: `3bfe268` (cbt.4.sec.zd6.per_ip — last `_failover_state` DoS gap closed). Run reached natural completion at ~3h30m of the 8h cap.

## What shipped this run — one paragraph

53 commits across five phases since fork from MAY04 tip `50750fe`. **Phase 1 (initial 33 commits)** delivered the planned two-bucket scope: cbt.1 receipt lift, cbt.2.{a, a.ui, b, c, c.timeout, c.large, bny} chat-UX hardening, cbt.3.{a–d, d.sweep} discovery refresh, cbt.4 client-side failover (five-bullet spec green), cbt.5/.6/.7/.8 plus all §17.G sub-beads, and the three operator-grade admin docs (`docs/admin/{discovery,failover,network-troubleshooting}.md`). **Phase 2** ran geoff against the shipped surface — `DISCOVERY_AUDIT.md` and `PARITY_REVIEW_MAY05.md` fed the post-ship critique loop. **Phase 3** closed the residual edit-save flake (Saturn-9ha mid-stream-edit drift, retiring the cbt.2.d / Saturn-ao6 family at 5/5) and added a security wave on `/api/system/chat`: admin-token gate (Saturn-zor / cbt.4.sec.token), bounded `_failover_state` with TTL + LRU (Saturn-zd6), per-IP cap (Saturn-68j), VPN/tunnel iface filter (Saturn-zt2), tightened v6 scope filter (Saturn-x9c), and peer-name hashing in `saturn_meta.routing` (Saturn-b3o amend). **Phase 4** consumed geoff's `FAILOVER_SECURITY.md` audit and shipped four P1/P2 hardenings: SSRF-resistant `api_base` TXT sanitisation (Saturn-xqw), operator-asserted name→node_id allowlist closing the TOFU pin-race (Saturn-93w), full-TXT (not just `models`) sanitisation (Saturn-eon), and `/api/discover` rate limiting (Saturn-jfs). **Phase 5 (idle artifacts)** brought gullivan's `SPLIT_BRAIN_PATTERNS.md` research synthesis; brutus `CHEATSHEET.md` and `RUN_INDEX_MAY05.md` are the next idle slots if the run continues.

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

### Phase 2 — post-ship critique loop

- `DISCOVERY_AUDIT.md` (geoff) — shipped earlier in the run; re-cited here because Phase 2 wired it back into the spec/code parity discussion.
- **`PARITY_REVIEW_MAY05.md`** (geoff, new) — review of `saturn/mdns/{txt, isolation, interfaces}.py` + `ServiceRecord` schema additions against `PRE_SPECS_B3.md §17.G.{1–4}`. Headline: three modules shipped clean as standalone surfaces with passing tests; the §17.G integration points (advertiser→validate, userspace→routable_addrs, web.py→probe) shipped in Phase 1's later wave (cbt.5.1, cbt.6.userspace, cbt.8.integrate) so the cited gaps were closed before this doc landed. Read PARITY_REVIEW as a snapshot of the integration boundary, not an open-issue list.
- `f7a2a01` post-ship demo wave-2 sweep — 8 integrate beads, 12 tests captured.

### Phase 3 — chat-UX residual + cbt.4 security wave

- `dcf235b` **Saturn-9ha** — Web-UI aborts the in-flight stream before re-sending on edit-save. Closes the cbt.2.d family (Saturn-ao6 retired at 5/5).
- `f868d50` post-fix demo for 9ha (mid-stream edit drift) — closes the bombadil prong-D failure called out at first-draft land.
- `b6ab724` **Saturn-zor — cbt.4.sec.token** — admin-token gate on `/api/system/chat`. The handler accepted any LAN HTTP request before; now requires the same bearer the rest of `/api/{services,admin,system,mcp}/*` enforces (qj5.16.2 lineage).
- `8c91f1f` **Saturn-zd6** — `_failover_state` is now bounded: TTL + LRU cap on the conversation-id → peer-name map. Closes the P1 from `FAILOVER_SECURITY.md` headline (header-spray DoS).
- `7222aba` **Saturn-68j — cbt.4.sec.zd6.per_ip** — per-IP cap on `_failover_state` insertions. Closes the residual gap where one IP could still consume the entire LRU before the global cap fires.
- `5eac74a` **Saturn-zor amend** (geoff P3) — caps `BrutusChat.messages` at 200. Bounds the unbounded-list memory-pressure surface called out in FAILOVER_SECURITY §1.
- `01808b9` **Saturn-b3o amend** (geoff P2) — peer names in `saturn_meta.routing.events` are now hashed; a curious receipt reader can't enumerate the peer set. Hash domain is per-process so receipts within a turn correlate.
- `0709ad6` **Saturn-zt2** — isolation probe filters VPN / tunnel / container interfaces. Prevents a Tailscale or Docker-bridge interface from masking real AP-isolation conditions.
- `56ee730` **Saturn-x9c** — IPv6 scope filter tightened: ULA / 6to4 / Teredo / mixed-case `fe80:` link-local all properly excluded from advertise-side address selection. Closes the partial-correctness call-out in FAILOVER_SECURITY §AAAA.
- `332d537` / `0317a24` post-ship demo captures for the cbt.4.sec.{token, ratelimit} chain plus cross-client + amendments.

### Phase 4 — geoff FAILOVER_SECURITY P1 chain

- **`FAILOVER_SECURITY.md`** (geoff, new) — security audit of cbt.4 + wave-2 mDNS surface. Headline P1: unbounded `_failover_state` (closed Phase 3 via Saturn-zd6 + Saturn-68j). Three additional P1/P2 findings filed and closed in this phase:
- `127f708` **Saturn-xqw — P1** — `api_base` TXT sanitised against SSRF. A hostile peer can no longer publish `api_base=http://internal.corp/admin` and have a Saturn client follow it; URLs are validated, only http/https schemes accepted, no internal/loopback hosts unless the operator opts in.
- `5930a72` **Saturn-93w — P1** — operator-asserted `name → node_id` allowlist closes the TOFU pin-race. The cbt.3.c flock + qj5.16.13.3 confirmation gate already closed the cross-process race; 93w shuts the *first-hostile-advertise-wins* window for new names.
- `b19fb80` **Saturn-eon — P2** — discovery sanitises **all** TXT values, not just `models`. `capabilities`, `features`, `api_base`, and any future TXT field are scrubbed for control characters, length, and shape before the runner consumes them.
- `4330b4d` **Saturn-jfs — P2** — `/api/discover` rate-limited. The endpoint hits zeroconf/Bonjour on every call; an unauthenticated client could blow the multicast budget. Same per-IP RPM bucket as the rest of `/api/*`.
- `3bfe268` / `89a2353` post-ship demo captures for xqw / 93w / eon / jfs and the per-IP zd6 close.

### Phase 5 — idle artifacts

When the run reached natural completion, idle crew picked up adjacent artifacts not in the original brief:

- **`SPLIT_BRAIN_PATTERNS.md`** (gullivan, new) — research synthesis on detection / resolution patterns from etcd, Consul, ZooKeeper, mDNS conflict resolution, and DNS resolver tie-breaking. Frame: Saturn is **not** a consensus system; the relevant analogue is *client-side leader hints*, not Raft. Feeds future split-brain work without committing to an implementation path.
- **`CHEATSHEET.md`** (brutus, expected) — operator quick-reference. Slot reserved; fill on next run if not landed before final push.
- **`RUN_INDEX_MAY05.md`** (writer, expected) — flat index of every artifact produced in this run for quick re-entry. Slot reserved.

## Crew

- New crew member **`bombadil`** spawned by forge to own the UI lane. Took cbt.2.a.ui (Saturn-3t8) and cbt.2.b (Saturn-6g1); follow-up edit-save re-attestation on cbt.bny.
- Crew tally: per-pane shortlog is collapsed into one author on the public branch; per-crew attribution lives in `.brutus/<bead>/transcript.md` and `crew list`.

## Bead status

### Closed this run — 38 beads

**Phase 1 — Bucket A (polish):** `Saturn-cbt.1`, `Saturn-c4n` (cbt.2.c), `Saturn-ex3` (cbt.2.c.timeout), `Saturn-eic` (cbt.2.c.large), `Saturn-bny` (cbt.bny), `Saturn-3t8` (cbt.2.a.ui), `Saturn-6g1` (cbt.2.b).

**Phase 1 — Bucket B.1 (discovery):** `Saturn-o6a` (cbt.3.a), `Saturn-nu4` (cbt.3.b), `Saturn-3to` (cbt.3.c), `Saturn-6m1` (cbt.3.d), `Saturn-an5` (cbt.3.d.sweep).

**Phase 1 — Bucket B.2 (failover):** `Saturn-cbt.4`.

**Phase 1 — Bucket B.3 (mDNS edges):** `Saturn-cbt.5`, `Saturn-5yh` (cbt.5.1), `Saturn-cbt.6`, `Saturn-pcj` (cbt.6.userspace), `Saturn-cbt.7`, `Saturn-9rv` (cbt.7.advertise), `Saturn-1xh` (cbt.7.resolve), `Saturn-76f` (cbt.7.prefer), `Saturn-7sg` (cbt.7.dedup), `Saturn-cbt.8`, `Saturn-bfx` (cbt.8.integrate).

**Phase 1 — carry-over:** `Saturn-qj5.16.13.3`.

**Phase 3 — chat-UX residual + cbt.4 security:** `Saturn-9ha` (cbt.2.d-D mid-stream edit drift), `Saturn-ao6` (cbt.2.d family closer), `Saturn-3d9` (cbt.5.1.ui), `Saturn-zor` (cbt.4.sec.token + amend), `Saturn-zd6` (bounded `_failover_state`), `Saturn-68j` (per-IP cap), `Saturn-zt2` (VPN/tunnel iface filter), `Saturn-x9c` (v6 scope tighten), `Saturn-b3o` (routing peer-name hash).

**Phase 4 — FAILOVER_SECURITY P1 chain:** `Saturn-xqw` (api_base SSRF), `Saturn-93w` (allowlist closes pin-race), `Saturn-eon` (full-TXT sanitise), `Saturn-jfs` (`/api/discover` rate limit).

### In-progress at land

None. The run reached natural completion. All called-out beads closed.

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

`git log --oneline 50750fe..autonomous/promo-push` → 53 commits. Tip: `3bfe268`.

Phases:

- **Phase 1** (33 commits) — `4f05fdb`…`c53760c`. Two-bucket scope, three admin docs, demo waves at `cb8d525` / `6ac80be` / `e15f599` / `2138ce4`. First handover draft at `0244ab9`; land-the-plane refresh at `d218085`; bd close sweep at `28be8c6`.
- **Phase 2** — `PARITY_REVIEW_MAY05.md` written; demo wave-2 sweep `f7a2a01`.
- **Phase 3** (10 commits) — `dcf235b` (9ha), `b6ab724` (zor), `8c91f1f` (zd6), `7222aba` / `3bfe268` (68j), `5eac74a` (zor amend), `01808b9` (b3o amend), `0709ad6` (zt2), `56ee730` (x9c). Demo `332d537` + `0317a24` + `f868d50`.
- **Phase 4** (5 commits) — `127f708` (xqw), `5930a72` (93w), `b19fb80` (eon), `4330b4d` (jfs), demo `89a2353`.
- **Phase 5** — `SPLIT_BRAIN_PATTERNS.md` (gullivan); CHEATSHEET.md / RUN_INDEX_MAY05.md slots reserved.

## Test counts

`saturn/tests/test_*.py` count at land: **72 test files**, ~30 of which are new this run (cbt.* lineage and security-wave additions). Brutus VERDICTs across the run carry per-bead pass counts; aggregate refresh into a `FINAL_VERDICT_MAY05.md` is brutus's idle slot if the run continues.

Phase 1 spot checks (all green at land):

- `test_failover_cbt4.py` — 4/4 (cbt.4 VERDICT, `4f05fdb`).
- `test_isolation_cbt5.py` — green (cbt.5 VERDICT, `5c7410c`).
- `test_routable_addrs_cbt6.py` — green (cbt.6 VERDICT, `f99354d`).
- `test_dual_stack_cbt7.py` — green (cbt.7 VERDICT chain, `d30e014` + sub-beads).
- `test_txt_validate_cbt8.py` — green (cbt.8 VERDICT, `173ad9e`).
- `test_discovery_settle_cbt3a.py`, `test_discovery_max_age_cbt3d.py`, `test_known_nodes_cross_proc_cbt3c.py`, `test_userspace_parallel_resolve_cbt3b.py` — all green.
- `test_mcp_edges_cbt2c.py`, `test_mcp_timeout_ex3.py`, `test_mcp_large_eic.py`, `test_long_messages_cbt2a.py` — green.

Phase 3 + 4 security wave (all green at land):

- `test_failover_sec_token` — Saturn-zor admin-token gate.
- `test_failover_state_bounded` — Saturn-zd6 TTL+LRU; per-IP cap variant for Saturn-68j.
- `test_isolation_iface_filter` — Saturn-zt2 VPN/tunnel exclusion.
- `test_v6_scope_filter` — Saturn-x9c ULA/6to4/Teredo/case-insensitive fe80.
- `test_routing_meta_hash` — Saturn-b3o peer-name hashing.
- `test_api_base_sanitize` — Saturn-xqw SSRF.
- `test_tofu_allowlist` — Saturn-93w pin-race close.
- `test_txt_sanitize_all` — Saturn-eon full-TXT.
- `test_discover_rate_limit` — Saturn-jfs.

Bombadil `chat` spec — playwright captures recorded for cbt.2.{a.ui, b}, cbt.bny, cbt.9ha; see `LANDING_DEMO.md` §8.

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
| `PARITY_REVIEW_MAY05.md` | _New this run_ — geoff's spec/code parity review of `saturn/mdns/{txt,isolation,interfaces}.py` against §17.G.{1–4}. |
| `FAILOVER_SECURITY.md` | _New this run_ — geoff's security audit of cbt.4 + wave-2 mDNS surface. Headline P1 closed mid-run; remaining findings filed and shipped Phase 3+4. |
| `SPLIT_BRAIN_PATTERNS.md` | _New this run_ — gullivan's research synthesis on detection/resolution patterns; framing for future split-brain work. |
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

> Resume `autonomous/promo-push`. Branch tip: `3bfe268`. MAY05 ran to natural completion at ~3h30m of the 8h cap with **38 beads green** across five phases: cbt.{1,4,5,6,7,8} + cbt.3.{a,b,c,d,d.sweep} + cbt.2.{a,a.ui,b,c,c.timeout,c.large,bny,9ha,ao6} + cbt.5.1.ui (Phase 1+3); the Phase 3 cbt.4 security wave (zor/zd6/68j/zt2/x9c/b3o); the Phase 4 FAILOVER_SECURITY P1 chain (xqw/93w/eon/jfs); plus carry-over qj5.16.13.3. No beads in_progress at land. Open follow-ups filed this run but not closed: `Saturn-oqh` (config plumbing for new mDNS env knobs `SATURN_ADVERTISE_ALL` / `SATURN_PREFER_V6` / `SATURN_TXT_CEILING`), `Saturn-b5a` / `Saturn-5ir` (cbt.5 Web-UI + adversarial), `Saturn-v60` (demo capture vs test fixture single-source), `Saturn-3bq` (`SATURN_ADMIN_PASSWORD` env for bombadil), `Saturn-b46` (TXT models for custom-module servers). MAY04 P2/P3 carry-overs are still open and not blocking; map in `RUN_NOTES_MAY04.md`. Operator docs landed at `docs/admin/{discovery, failover, network-troubleshooting}.md`; wire them into `docs/index.md` if a Diátaxis pass is in scope. Idle artifacts available for next-run scaffolding: `SPLIT_BRAIN_PATTERNS.md` (split-brain research, no implementation committed), `PARITY_REVIEW_MAY05.md` (post-ship integration snapshot), `FAILOVER_SECURITY.md` (geoff audit, all P1 closed). `CHEATSHEET.md` (brutus) and `RUN_INDEX_MAY05.md` (writer) are reserved Phase-5 idle slots — pick up if scope allows. Start with `bd ready`.
