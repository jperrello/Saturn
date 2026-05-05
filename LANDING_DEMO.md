# LANDING_DEMO — promo-push run, May 2026

Every visible UI / CLI / HTTP behavior change in this run has a reproducer
on disk. The reproducers are showboat-executable: each `*.md` below
embeds a captured-output block. **Run `uvx showboat verify <file>` on
any of them to catch drift** — the verifier re-executes the embedded
shell blocks and diffs the new output against the snapshot.

The harness underneath every visual capture lives in `tests/harness/`
(real Saturn web subprocess + admin/runner bearers + isolated
SATURN_DATA_DIR) and `demo/recordings/_capture_*.py` (Playwright +
add_init_script + page.route auth wrapper).

---

## 1 · Foundation: real-Saturn test harness

| Bead | Commit(s) | Artifact | Headline |
|------|-----------|----------|----------|
| qj5.7 | `f195dbd`, `c4f9a19` | [`tests/harness/README.md`](tests/harness/README.md) | Python primitives + CLI for end-to-end verification against a real Saturn server. `bash tests/harness/run.sh` smokes ollama + mDNS + saturn web + OpenRouter mgmt API. Regression-pass after qj5.16.{1,2} bearer auth landed: probes 401/401/200 on `/v1/health` and `/api/services`. |

## 2 · Defensive auth captures

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| qj5.16.1 | `90f1e26` | [`demo/recordings/qj5.16.1-runner-auth.md`](demo/recordings/qj5.16.1-runner-auth.md) | Runner `/v1/*` bearer gate: 401 (no bearer) / 401 (wrong) / 200 (correct), `WWW-Authenticate: Bearer` on the 401s. |
| qj5.16.2 | `90f1e26` | [`demo/recordings/qj5.16.2-admin-auth.md`](demo/recordings/qj5.16.2-admin-auth.md) | Web admin `/api/*` bearer gate: same 401-401-200 triplet. |

## 3 · Chat-UX retroactive captures (Bucket 1)

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| qj5.1 | `83386fd` | [`qj5.1-style-pill-removed.md`](demo/recordings/qj5.1-style-pill-removed.md) | Top-right `Default ▾` style pill removed from the chat strip. |
| qj5.2 | `74c98aa` | [`qj5.2-settings-popup.md`](demo/recordings/qj5.2-settings-popup.md) | Saturn SVG → "Settings" button + per-chat popup (style / model / service). |
| qj5.3 | `74c98aa` | [`qj5.3-mcp-popup.md`](demo/recordings/qj5.3-mcp-popup.md) | MCP TOOLS gains a visible label + Add-MCP-server form unhidden. |
| qj5.4 | `74c98aa` | [`qj5.4-plus-menu.md`](demo/recordings/qj5.4-plus-menu.md) | 5 unlabelled icons collapsed into a single `+` menu (Attach + MCP/Connectors). |
| qj5.5 | `6b5b64d`, `83386fd` | [`qj5.5-send-aligned.md`](demo/recordings/qj5.5-send-aligned.md) | Send button vertically aligned with the chat input (`align-items:center; align-self:stretch`). |
| qj5.6 | `74c98aa` | [`qj5.6-edit-message.md`](demo/recordings/qj5.6-edit-message.md) | Edit-sent-message: textarea + Save & regenerate / Cancel — Claude/ChatGPT-style truncate-and-regenerate. |

## 4 · Boot-time security (Bucket 3)

| Bead | Commit(s) | Artifact | Headline |
|------|-----------|----------|----------|
| qj5.14 | `5c9f96e`, `b75305f` | [`qj5.14-boot-fail.md`](demo/recordings/qj5.14-boot-fail.md) | 12-case violation matrix: 10/11 bad rows now `exit=1 saturn: config error: …`; the legitimate `SATURN_DEV_MODE=1` escape and the green-path stay `ALIVE`. |
| qj5.16.3 | `c222dca`, `9d75f13` | [`qj5.16.3-trusted-proxies.md`](demo/recordings/qj5.16.3-trusted-proxies.md) | XFF spoof gate: empty allowlist now refuses XFF (case 1), untrusted peer falls back to socket (case 3), live POST `/api/admin/config` lifts trusted_proxies without restart (case 5). Cases 2+4 stay green. |

## 5 · Configure page (Bucket 3)

| Bead | Commit(s) | Artifact | Headline |
|------|-----------|----------|----------|
| qj5.13 | `51e22ab` | [`qj5.13-configure-page.md`](demo/recordings/qj5.13-configure-page.md) | Server-side admin-config round-trip: POST `rate_rpm=99` → GET `{"rate_rpm":99}` against an isolated SATURN_DATA_DIR. |
| Saturn-hft | `bb3d259`, `c222dca` | [`qj5.hft-configure-ui.md`](demo/recordings/qj5.hft-configure-ui.md) | Admin Configure page server-renders the 8-group AdminConfig schema with inline values; `rate_rpm=137` inlined pre-paint at `/admin/configure`. Carries the qj5.13.7 no-bearer regression guard (see below). |
| qj5.13.7 | `c9347a0` (guard), `f582af7` (post-fix) | (folded into hft doc) | No-bearer SSR-leak regression on `/admin/configure` caught by the probe (200 with 8 admin fields visible) → fixed by restoring `Depends(require_admin)`; matrix flips to 401-401-401. |
| Saturn-6sb | `bb3d259`, `ed448c5` | [`qj5.6sb-per-service-editor.md`](demo/recordings/qj5.6sb-per-service-editor.md) | Per-service editor on the Configure page: `plaintext api-key inputs` flips 1→0 (the legacy `#cfg-api-key` is gone; new `#cfg-api-key-env` reads "API key — env var NAME (never the key value)"). `api_key_env` / `max_budget_usd` / `require_runner_token` surface. |
| Saturn-7j3 | `2ed5252`, `9325c5e` | [`qj5.7j3-known-nodes-ui.md`](demo/recordings/qj5.7j3-known-nodes-ui.md) | Known-nodes UI: trust_mode dropdown (carryover) + allowlist picker rendering `/api/admin/known-nodes` + pending-rejections table with Attest / Forget actions. 4-surface audit GREEN. |

## 6 · Per-turn applied-config receipt

| Bead | Commit(s) | Artifact | Headline |
|------|-----------|----------|----------|
| qj5.15 | `cc92207`, `f106fee` | [`qj5.15-receipt-envelope.md`](demo/recordings/qj5.15-receipt-envelope.md) | `saturn_meta` envelope on `/api/chat` SSE stream: schema_version=1, applied values read from upstream (max_tokens / model / finish_reason / system_prompt_sha256 + preview), `verifiability.top_p="requested-not-verifiable"`, `diff.coerced=[]`. The Configured-vs-Applied two-column is the screen the user reads. |

## 7 · Beacon hardening

| Bead | Commit(s) | Artifact | Headline |
|------|-----------|----------|----------|
| qj5.16.4 | `ed448c5`, `50750fe` | [`qj5.16.4-beacon-budget.md`](demo/recordings/qj5.16.4-beacon-budget.md) | Provider `payload()` now accepts `max_budget_usd` and emits `limit` (OpenRouter) / `max_budget_usd` (DeepInfra). DeepInfra `revoke()` flipped from `pass` to a real DELETE. Freshness ratio 600/400 = 1.50 (was 2.00). `AdminConfig.beacon_max_budget_usd` threaded through `CredentialManager`. |
| qj5.16.14 | `cc92207`, `50750fe` | [`qj5.16.14-sleep-transition.md`](demo/recordings/qj5.16.14-sleep-transition.md) | Beacon unregister-on-sleep + re-mint-on-wake. 11/11 §17.E.6 contract tests pass; directed trace shows BEFORE/SLEEP/WAKE with `rotated=True` — the published TXT after wake never carries the pre-sleep credential. |

---

## 8 · MAY05 run — phase-grouped view

### TL;DR

| Phase | Theme | Beads | Commits |
|-------|-------|-------|---------|
| 1 | Discovery + failover + dual-stack (original cbt.1-4 ship + Wave-2 wiring) | 18 | 18 |
| 2 | Chat-UX hardening (cbt.2.* family + edit-save) | 8 | 5 (+ 3 regression/UI) |
| 3 | Security + cross-client (cbt.4.sec.* + ggn cross-client + 4 amendments) | 7 | 5 (+ 2 regression-guards) |
| 4 | P1 audit-driven (xqw / 93w / eon / jfs / zd6 / 68j) | 6 | 6 |
| **Total** | | **39** | **34 + 5 guards/specs** |

User-facing entry points:

  - **[`FAILOVER_DEMO.md`](FAILOVER_DEMO.md)** — 60-second README of the cbt.4 receipt-aware failover (real Saturn, real Ollama, kill-A-mid-stream).

### Idle artifacts (pointer block)

These exist on disk and are still useful as reference reading; they are
not refreshed per-batch so treat their content as a snapshot.

  - [`SPLIT_BRAIN_PATTERNS.md`](SPLIT_BRAIN_PATTERNS.md) — failure-mode taxonomy for trust-anchor splits.
  - [`.brutus/CHEATSHEET.md`](.brutus/CHEATSHEET.md) — brutus contract conventions.
  - [`RUN_NOTES_MAY04.md`](RUN_NOTES_MAY04.md) / [`RUN_NOTES_MAY05.md`](RUN_NOTES_MAY05.md) — session handover docs.
  - [`PRE_SPECS_B3.md`](PRE_SPECS_B3.md) — implementer pre-specs (§17 series).
  - [`DISCOVERY_AUDIT.md`](DISCOVERY_AUDIT.md) — discovery-layer audit referenced by cbt.3.\* beads.
  - [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) — security-audit findings referenced by Phase-3 / Phase-4.
  - [`FINAL_AUDIT_SUMMARY.md`](FINAL_AUDIT_SUMMARY.md) / [`FINAL_VERDICT.md`](FINAL_VERDICT.md) — MAY04-run aggregates.

### Phase 1 — discovery + failover + dual-stack (18 beads / 18 commits)

cbt.1 receipt + cbt.4 failover ship the headlines; cbt.3.\* tunes the
discovery layer underneath; cbt.5/6/7/8 land their components in this
phase, with the Wave-2 integrate beads wiring them through the
publisher/resolver/dispatcher.

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| cbt.1 | `347bdc9` | [`cbt.1-receipt-lift.md`](demo/recordings/cbt.1-receipt-lift.md) | `saturn_meta` envelope lifted onto `/api/proxy/chat` (SSE meta line) and runner `/v1/chat/completions` (stream + non-stream). Three surfaces green via `test_receipt_meta_lift.py` against real Ollama. |
| cbt.4 | `4f05fdb` | [`cbt.4-failover.md`](demo/recordings/cbt.4-failover.md) | Client-side failover on `/api/system/chat`: active 5xx → switch in 130 ms (cap 2 s); sticky session pinned by `X-Saturn-Conversation-Id`; per-model affinity fails loud; `saturn_meta.routing.events` records every switch. Two-peer subprocess harness via `cbt.4_failover_probe.sh`. |
| cbt.3.a | `75c58f9` (Saturn-o6a) | [`cbt.3.a-settle-plumb.md`](demo/recordings/cbt.3.a-settle-plumb.md) | One-line fix: `discover()` now passes `settle_time` into `SettleDetector(...)` instead of dropping it on the floor. Test asserts wall-clock tracks the requested value across two distinct settle settings; real Zeroconf on `127.0.0.1`, no mocks. |
| cbt.3.b | `2c9ef90` (Saturn-nu4) | [`cbt.3.b-worker-pool.md`](demo/recordings/cbt.3.b-worker-pool.md) | `_Listener` resolves moved off the zeroconf engine thread onto a `queue.Queue` + 8 persistent workers with per-`(action,name)` in-flight dedupe. Kills the 30-second backlog when 10 services arrive at once. |
| cbt.3.c | `8d2bbfd` (Saturn-3to) | [`cbt.3.c-cross-proc-lock.md`](demo/recordings/cbt.3.c-cross-proc-lock.md) | `fcntl.flock(LOCK_EX)` on a sibling `.lock` file wraps every `known_nodes` mutator. Falsified via real-subprocess fan-out test: every concurrent `pin()` survives. Closes the lost-write race that broke the qj5.7j3 + qj5.16.13 trust anchor. |
| cbt.3.d | `fa57189` (Saturn-6m1) | [`cbt.3.d-last-seen-max-age.md`](demo/recordings/cbt.3.d-last-seen-max-age.md) | `SaturnService.last_seen` populated on every add/update; `discover(max_age=…)` filters zombies. Default kwarg None preserves prior behaviour. Active health sweep deferred to cbt.3.d.sweep. |
| cbt.3.d.sweep | `c53760c` (Saturn-an5) | [`cbt.3.d.sweep-stale.md`](demo/recordings/cbt.3.d.sweep-stale.md) | `SaturnDiscovery.sweep_stale(max_age)` — in-memory eviction half of DISCOVERY_AUDIT (d). Pops every `last_seen < now - max_age` entry under `self.lock`; returns evicted `node_id` list. Health-driven sweep still tracks under cbt.3.d.sweep.health. |
| cbt.5 | `5c7410c` | [`cbt.5-isolation-probe.md`](demo/recordings/cbt.5-isolation-probe.md) | `saturn/mdns/isolation.py`: `IsolationProbe` + `probe(timeout)` advertises a transient `_saturn-probe._tcp.local.` and browses for it from the same engine; loopback green, isolation branch falsifiable via `UserspaceBackend.fault_filter`. Repro notes in [`cbt.5_ap_isolation_repro.md`](demo/recordings/cbt.5_ap_isolation_repro.md). |
| cbt.5.1 | `b6b184f` (Saturn-5yh) | [`cbt.5.1-api-discover-isolation.md`](demo/recordings/cbt.5.1-api-discover-isolation.md) | `GET /api/discover` now returns `{services, isolation}` per §17.G.1.3; `isolation` is `IsolationProbe.asdict()` from a once-per-request `run_in_executor` probe. Web-UI/app.js bumps to read `body.services` and caches `window.saturnIsolation` for the cbt.5.1.ui render bead. |
| cbt.6 | `f99354d` | [`cbt.6-routable-addrs.md`](demo/recordings/cbt.6-routable-addrs.md) | `saturn/mdns/interfaces.py::routable_addrs()` returns non-loopback / non-link-local IPv4 on UP interfaces via `psutil`. `psutil>=5.9.0` formalised in `pyproject`. Carrier for the multi-NIC advertise fix (cbt.6.integrate). |
| cbt.6.userspace | `78b0a64` (Saturn-pcj) | [`cbt.6.userspace-multi-addr.md`](demo/recordings/cbt.6.userspace-multi-addr.md) | `UserspaceBackend.advertise()` now binds every `routable_addrs()` result instead of a single `get_lan_ip()`; falls back to `[get_lan_ip()]` when nothing routable. Multi-NIC hosts publish one A per routable address — clients on the other interface finally see the service. |
| cbt.7 | `d30e014` | [`cbt.7-dual-stack-schema.md`](demo/recordings/cbt.7-dual-stack-schema.md) | Schema-only carrier for IPv6: `ServiceRecord.addresses` + `SaturnService.{addresses, ipv6}`; `host` stays back-compat. A/AAAA advertise + prefer-v6 routing track separately. |
| cbt.7.resolve | `0ccab52` (Saturn-1xh) | [`cbt.7.resolve-userspace.md`](demo/recordings/cbt.7.resolve-userspace.md) | Userspace `_resolve()` walks `addresses_by_version(IPVersion.All)` and dispatches per family (`inet_ntoa` / `inet_ntop(AF_INET6)`). `ServiceRecord.addresses` carries the full v4+v6 list; `host` stays first entry for back-compat. Bonjour/Avahi resolve plumbing tracks separately. |
| cbt.7.advertise | `e7b6adf` (Saturn-9rv) | [`cbt.7.advertise-dual-stack.md`](demo/recordings/cbt.7.advertise-dual-stack.md) | `routable_addrs(family='v4'\|'v6'\|'both')` extends the cbt.6 helper; `UserspaceBackend.advertise()` packs A + AAAA into one Zeroconf `ServiceInfo`. Publish-side counterpart to cbt.7.resolve. |
| cbt.7.dedup | `189a86d` (Saturn-7sg) | [`cbt.7.dedup-merge.md`](demo/recordings/cbt.7.dedup-merge.md) | `_to_service()` populates `addresses` + `ipv6` from `ServiceRecord.addresses`; `_add()` merges into existing entries by `node_id` instead of overwriting. Dual-stack peers no longer appear twice in `discover()` — kills the duplicate-priority / phantom-failover-slot bug. |
| cbt.7.prefer | `3a2cc30` (Saturn-76f) | [`cbt.7.prefer-v6.md`](demo/recordings/cbt.7.prefer-v6.md) | `saturn.discovery.connect_address(service)` returns the dial address; default = first IPv4, `SATURN_PREFER_V6=1` flips to v6 when both families present, falls back to v4 when only v4 advertised. 3/3 prongs. |
| cbt.8 | `173ad9e` | [`cbt.8-txt-validate.md`](demo/recordings/cbt.8-txt-validate.md) | `saturn/mdns/txt.py`: `TXT_SAFE_CEILING=1200`, `TxtTooLarge`, `validate(props) -> int`. Returns RFC 6763 §6.1 wire bytes; raises on per-entry >255 B or total >ceiling. |
| cbt.8.integrate | `6df7367` (Saturn-bfx) | [`cbt.8.integrate-mtrunc.md`](demo/recordings/cbt.8.integrate-mtrunc.md) | `SaturnAdvertiser._properties()` joins models + capabilities raw, then prunes (model → capability → features) until `txt.validate()` passes; records dropped count under `mtrunc=`. Unprunable bloat raises `TxtTooLarge` at register time. Wires the cbt.8 ceiling into the advertiser path. |

### Phase 2 — chat-UX hardening (8 beads / 5 commits + 3 regression/UI specs)

cbt.2.\* family across the chat surface — long-message streaming, attachments,
MCP edges, and the edit-save / mid-stream-edit drift.

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| cbt.2.a | regression-guard | [`cbt.2.a-long-messages.md`](demo/recordings/cbt.2.a-long-messages.md) | HTTP-layer regression guard for >4k-token messages: 200 SSE, time-to-first-byte <5s, receipt with `prompt_tokens ≥ 1000`. UI-freeze proof tracks under Saturn-3t8. |
| cbt.2.a.ui | Saturn-3t8 (bombadil) | [`cbt.2.a.ui-longstream.md`](demo/recordings/cbt.2.a.ui-longstream.md) | Bombadil/Playwright proof that the chat tab stays interactive across a 70 s long-stream turn: `ttfb=2.94 s`, `timer.p99=7.3 ms`, monotonic bubble + scroll, send button recovers, zero console errors. Final-frame screenshot embedded. |
| cbt.2.b | Saturn-6g1 (bombadil) | [`cbt.2.b-attachments.md`](demo/recordings/cbt.2.b-attachments.md) | Bombadil/Playwright proof for the `+`-menu attachment flow: allowed/disallowed file types, exact 100 KB boundary (=100 KB accepted, +1 byte rejected), `+` → attach hides menu, badge → remove clears input. All 7 oracle bullets green. |
| cbt.2.c.unreachable | `5ac0a28` | [`cbt.2.c-mcp-unreachable.md`](demo/recordings/cbt.2.c-mcp-unreachable.md) | `MCPClientManager.call()` unwraps `BaseExceptionGroup` so an unreachable MCP server reads `MCP server '<name>' unreachable at <url>: <inner>` instead of anyio's TaskGroup blob. Real closed-TCP-port test; no mocks. |
| cbt.2.c.timeout | `83633d3` (Saturn-ex3) | [`cbt.2.c.timeout-mcp.md`](demo/recordings/cbt.2.c.timeout-mcp.md) | `asyncio.wait_for(..., timeout=CALL_DEADLINE_S)` around the MCP invoke step kills the inherited 300 s `sse_read_timeout`. Hung tool aborts in <10 s; same error shape as the unreachable/large fixes. Real fake-MCP fixture sleeping 30 s. |
| cbt.2.c.large | `4961da8` (Saturn-eic) | [`cbt.2.c.large-mcp.md`](demo/recordings/cbt.2.c.large-mcp.md) | After `call_tool()`, sum text-content bytes; reject if `> LARGE_RESULT_BYTES = 1 MiB`. Model sees a single shaped error; chat-context budget preserved. Real fake-MCP fixture returning a 10 MiB blob. |
| cbt.bny | `417ba93` | [`cbt.bny-edit-save.md`](demo/recordings/cbt.bny-edit-save.md) + [`.png`](demo/recordings/cbt.bny-edit-save.png) | One-line `userDiv.remove()` in `Web-UI/app.js` save handler kills the orphan-DOM bug after Save-and-regenerate. Bombadil `edit_ao6` re-attestation: prongs A/B/C/E green; prong D's flip-to-FAIL exposes residual mid-stream-edit drift filed as **Saturn-9ha**. Re-attestation memo: [`.brutus/Saturn-ao6/RE-ATTESTATION.md`](.brutus/Saturn-ao6/RE-ATTESTATION.md). |
| Saturn-9ha | `dcf235b` | [`cbt.9ha-midstream-edit.md`](demo/recordings/cbt.9ha-midstream-edit.md) + [`.png`](demo/recordings/cbt.9ha-midstream-edit.png) | Save handler aborts the in-flight stream (sets `_userStopped`, calls `activeController.abort()`, polls ≤2 s for `sending===false`) before sibling-remove + `msgs.splice` + `send()`. Closes the cbt.2.d / Saturn-ao6 family: bombadil `edit_ao6` flips to **5/5 prongs green** (A/B/C/D/E). |

### Phase 3 — security + cross-client (7 beads / 5 commits + 2 regression-guards)

cbt.4.sec.\* hardening of the failover surface, cross-client `/v1/*`
contract pin, plus four amendment beads from geoff's review.

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| cbt.4.sec.token | `b6ab724` (Saturn-zor) | [`cbt.4.sec.token-auth.md`](demo/recordings/cbt.4.sec.token-auth.md) | `Depends(require_admin)` on `brutus_chat` — `/api/system/chat` was the lone `/api/system/*` surface without an auth gate. 401-401-200 matrix; cbt.4 fixture updated to inject the bearer (4/4 failover tests stay green). |
| cbt.4.sec.ratelimit | regression-guard (Saturn-b3o) | [`cbt.4.sec.ratelimit-guard.md`](demo/recordings/cbt.4.sec.ratelimit-guard.md) | `_check_rate` already wired into `brutus_chat`; b3o pins the invariant. With `SATURN_RATE_RPM=2`, 6 rapid POSTs yield ≥1 HTTP 429 with `Retry-After`; first 1-2 stay un-429'd (proves limit > 0). Real subprocess, no mocks. |
| cbt.cross-client | regression-guard (Saturn-ggn) | [`cbt.cross-client-guard.md`](demo/recordings/cbt.cross-client-guard.md) | Three HTTP stacks (`urllib` / `httpx` / `curl`) hit `/v1/{health,models,chat/completions}` (stream + non-stream) and return identical canonical forms (after stripping per-call `id` / `created`). Go deferred to **Saturn-ggn.go**. Pins the OpenAI-compatible contract before middleware drift. |
| cbt.4.sec.token amend | `5eac74a` (Saturn-zor.amend / geoff P3) | [`cbt.4.sec.token-amend-cap.md`](demo/recordings/cbt.4.sec.token-amend-cap.md) | `Field(max_length=200)` on `BrutusChat.messages`. Authorised callers can no longer drop a 10 000-element list into the failover loop; Pydantic rejects with HTTP 422 at validation time. Cap chosen at 200 per geoff's 200-500 recommendation. |
| cbt.4.sec routing-hash | `01808b9` (Saturn-b3o.amend / geoff P2) | [`cbt.4.sec.routing-hash.md`](demo/recordings/cbt.4.sec.routing-hash.md) | `_alias_peer(name) -> sha256(name)[:8]` wired through `routing.events[*].{from,to}` and `routing.service`. Receipt readers (admin-token holders / stolen-creds attackers) can no longer enumerate the peer mesh from `saturn_meta.routing`. Routing behaviour unchanged; only the shape of the names. |
| cbt.5 zt2 (tunnel filter) | `0709ad6` (Saturn-zt2) | [`cbt.5.zt2-tunnel-filter.md`](demo/recordings/cbt.5.zt2-tunnel-filter.md) | `TUNNEL_PREFIXES = ('tun','utun','wg','tap','docker','veth','ipsec','gif','stf')` skipped in `isolation._link_ifaces()`. Closes a VPN-posture leak via `/api/discover.isolation.ifaces_with_link` and stops `utun` from masking real isolation. |
| cbt.7 x9c (v6 filter) | `56ee730` (Saturn-x9c) | [`cbt.7.x9c-v6-filter.md`](demo/recordings/cbt.7.x9c-v6-filter.md) | `routable_addrs(family='v6')` now lowercases + rejects fe80::/10 (all cases), fc00::/7 ULA, 2002::/16 6to4, 2001::/32 Teredo (preserves 2001:db8::/32 docs). Stops cbt.7.advertise from packing unroutable v6 into AAAA. |

### Phase 4 — P1 audit-driven (6 beads / 6 commits)

External-audit hits triaged P1/P2/P3, all landed with falsifiable tests.

| Bead | Commit | Artifact | Headline |
|------|--------|----------|----------|
| Saturn-xqw | `127f708` | [`cbt.sec.xqw-api-base-ssrf.md`](demo/recordings/cbt.sec.xqw-api-base-ssrf.md) | **P1.** Peer-asserted `api_base` via TXT → SSRF (cloud metadata at 169.254.169.254, loopback, RFC-1918, CGNAT, link-local, ULA). Saturn now classifies the resolved host at the dispatch boundary and refuses the dangerous prefixes; public-host control still passes. |
| Saturn-93w | `5930a72` | [`cbt.sec.93w-tofu-allowlist.md`](demo/recordings/cbt.sec.93w-tofu-allowlist.md) | **P1.** TOFU pin-race fix. New `~/.saturn/allowlist.json` `name → node_id` map consulted **before** TOFU in `_classify_trust()`; the legit `node_id` is authoritative and squatters get `rebind_rejected`. Closes the "stuck-in-bad-state forever" failure mode in the trust-anchor chain. |
| Saturn-eon | `b19fb80` | [`cbt.sec.eon-txt-sanitize.md`](demo/recordings/cbt.sec.eon-txt-sanitize.md) | **P2.** `_sanitize_txt_value` mapped over **all** TXT values, not just `models` (`api_base`, `dep`, `deployment`, `api_type`, `cost`, …). Strips `\n` / `\r` / `\x00`; legitimate URL chars preserved. Defense-in-depth atop xqw at the parser entrance. |
| Saturn-jfs | `4330b4d` | [`cbt.sec.jfs-discover-rate.md`](demo/recordings/cbt.sec.jfs-discover-rate.md) | **P2.** `/api/discover` (5 s `discover()` + 4 s `isolation.probe()` ≈ 9 s blocking) was un-rate-limited; 6 attacker requests forced 54 s of amplification. Handler now `_check_rate`'s at entry — 429 + `Retry-After` mirrors `/api/chat` / `/api/system/chat`. |
| Saturn-zd6 | `8c91f1f` | [`cbt.4.sec.zd6-bounded-sticky.md`](demo/recordings/cbt.4.sec.zd6-bounded-sticky.md) | **P1.** `_failover_state` was a plain unbounded `dict` — attacker spraying unique `X-Saturn-Conversation-Id` values grew RSS without bound. Replaced with `_StickyMap(OrderedDict)`: `MAX_STICKY=10000` LRU cap via `popitem(last=False)`, per-entry TTL (`STICKY_TTL_S=3600`) checked on read, expired purge on insert. |
| Saturn-68j | `7222aba` (lineage: zd6 / `8c91f1f`) | [`cbt.4.sec.68j-per-ip-sticky.md`](demo/recordings/cbt.4.sec.68j-per-ip-sticky.md) | **P3.** Last DoS gap on `_failover_state`. zd6 capped the map globally + added TTL; one hostile IP could still burn all 10 000 slots and evict legit pins via global FIFO. 68j adds `MAX_STICKY_PER_IP=100` via `_StickyMap._by_ip`; per-IP eviction runs first, global FIFO drops IP-bucket references on overflow. |

## How to use this on re-entry

1. **`bash tests/harness/run.sh`** — smoke the harness against the
   current Saturn install. Must pass before any of the captures
   below will run cleanly.
2. **Pick any row.** Open the linked `.md` to read the framing,
   then `uvx showboat verify demo/recordings/<file>.md` to confirm
   the captured behaviour still holds.
3. **For UI captures**, the reproducer command is at the foot of
   each doc — usually `LABEL=after PYTHONPATH=. python3
   demo/recordings/_capture_<bead>.py`.
4. **One bead remaining**: qj5.16.13.3 settle-pin race retro
   capture lands once hardener ships.
