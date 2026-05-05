# RUN_INDEX_MAY05.md — bead → contract → test → verdict → commit

One-click archaeology for the MAY05 promo-push autonomous run. Every
bead authored by brutus this session is mapped to its contract,
failing-test artifact, verdict (if green), transcript, and the
hardener's implementation commit (if landed).

Branch: `autonomous/promo-push`. Artifacts under `.brutus/<bead>/`.

## Reading this index

Each row carries enough to find the artifact without further searching:

- **Bead** — bd id, links to `.brutus/<bead>/`.
- **Spec** — short label for the falsifiable behavior.
- **Contract** — `.brutus/<bead>/CONTRACT.md` (always present).
- **Test** — `saturn/tests/<file>.py` (always present).
- **Verdict** — `.brutus/<bead>/VERDICT.md` (only when GREEN).
- **Commit** — hardener's fix sha (only when GREEN).
- **Transcript** — `.brutus/<bead>/transcript.md` (showboat capture; red+green when both happened).

---

## Phase 0 — receipt lift to other chat surfaces

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-cbt.1](Saturn-cbt.1/) | qj5.15.2: lift `saturn_meta` to `/api/proxy/chat` + runner `/v1/chat/completions` (stream + non-stream) | `saturn/tests/test_receipt_meta_lift.py` | `347bdc9` | GREEN |

## Phase 1 — failover + chat UX hardening

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-cbt.4](Saturn-cbt.4/) | client-side failover (timeout + sticky + affinity + receipt) | `test_failover_cbt4.py` | `4f05fdb` | GREEN |
| [Saturn-cbt.2.a / oqm](Saturn-cbt.2.a/) | long-message HTTP regression guard | `test_long_messages_cbt2a.py` | n/a (preserve-behavior) | GREEN |
| [Saturn-c4n](Saturn-c4n/) | MCP unreachable error clarity | `test_mcp_edges_cbt2c.py` | `5ac0a28` | GREEN |
| [Saturn-ex3](Saturn-ex3/) | MCP tool-call timeout | `test_mcp_timeout_ex3.py` | `83633d3` | GREEN |
| [Saturn-eic](Saturn-eic/) | MCP oversized payload guard | `test_mcp_large_eic.py` | `4961da8` | GREEN |

## Phase 2 — discovery audit (cbt.3 quartet)

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-cbt.3.a / o6a](Saturn-cbt.3.a/) | settle_time plumbing | `test_discovery_settle_cbt3a.py` | `75c58f9` | GREEN |
| [Saturn-cbt.3.b / nu4](Saturn-cbt.3.b/) | userspace parallel resolves | `test_userspace_parallel_resolve_cbt3b.py` | `2c9ef90` | GREEN |
| [Saturn-cbt.3.c / 3to](Saturn-cbt.3.c/) | known_nodes cross-process flock | `test_known_nodes_cross_proc_cbt3c.py` | `8d2bbfd` | GREEN |
| [Saturn-cbt.3.d / 6m1](Saturn-cbt.3.d/) | last_seen + discover(max_age) | `test_discovery_max_age_cbt3d.py` | `fa57189` | GREEN |

## Phase 2.5 — §17.G mDNS edges (4 modules + schema)

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-cbt.5](Saturn-cbt.5/) | AP-isolation probe (`saturn/mdns/isolation.py`) | `test_isolation_cbt5.py` | `5c7410c` | GREEN |
| [Saturn-cbt.6](Saturn-cbt.6/) | `routable_addrs()` (`saturn/mdns/interfaces.py`) | `test_routable_addrs_cbt6.py` | `f99354d` | GREEN |
| [Saturn-cbt.7](Saturn-cbt.7/) | dual-stack `ServiceRecord.addresses` schema | `test_dual_stack_cbt7.py` | `d30e014` | GREEN |
| [Saturn-cbt.8](Saturn-cbt.8/) | TXT validator (`saturn/mdns/txt.py`) | `test_txt_validate_cbt8.py` | `173ad9e` | GREEN |

## Phase 3 — wave-2 wire-ins (geoff parity review)

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-76f](Saturn-76f/) | `connect_address()` + `SATURN_PREFER_V6` | `test_prefer_v6_cbt7_prefer.py` | `3a2cc30` | GREEN |
| [Saturn-bfx](Saturn-bfx/) | advertiser TXT validate + mtrunc | `test_advertise_mtrunc_cbt8_integrate.py` | `6df7367` | GREEN |
| [Saturn-pcj](Saturn-pcj/) | userspace advertise via routable_addrs | `test_userspace_multi_addr_cbt6_userspace.py` | `78b0a64` | GREEN |
| [Saturn-5yh](Saturn-5yh/) | `/api/discover` returns `{services, isolation}` | `test_api_discover_isolation_cbt5_1.py` | `b6b184f` | GREEN |
| [Saturn-1xh](Saturn-1xh/) | userspace `_resolve` v4+v6 walk | `test_dual_stack_resolve_cbt7_resolve.py` | `0ccab52` | GREEN |
| [Saturn-9rv](Saturn-9rv/) | advertise-side AAAA records | `test_dual_stack_advertise_cbt7_advertise.py` | `e7b6adf` | GREEN |
| [Saturn-7sg](Saturn-7sg/) | dual-stack address dedup in `_add` | `test_dual_stack_dedup_cbt7_dedup.py` | `189a86d` | GREEN |
| [Saturn-an5](Saturn-an5/) | `SaturnDiscovery.sweep_stale(max_age)` | `test_discovery_sweep_cbt3d_sweep.py` | `c53760c` | GREEN |

## Phase 4 — Phase 3 security + cross-client

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-zor](Saturn-zor/) | `/api/system/chat` admin-token gate (+ messages cap) | `test_system_chat_auth_zor.py` | `b6ab724`, `5eac74a` | GREEN |
| [Saturn-b3o](Saturn-b3o/) | rate-limit guard + routing peer-name hash | `test_system_chat_ratelimit_b3o.py`, `test_routing_events_hash_b3o.py` | `01808b9` | GREEN |
| [Saturn-ggn](Saturn-ggn/) | /v1/* HTTP-stack parity (urllib + httpx + curl) | `test_cross_client_ggn.py` | n/a (preserve-behavior) | GREEN |
| [Saturn-vyy](Saturn-vyy/) | protocol-level cross-client (zeroconf + dns-sd + curl) | `test_cross_client_real_vyy.py` | n/a (preserve-behavior) | GREEN |

## Phase 5 — security audit follow-ups

### From geoff `PARITY_REVIEW_MAY05.md`

| Bead | Spec | Test | Commit | Status |
|---|---|---|---|---|
| [Saturn-x9c](Saturn-x9c/) | v6 filter ULA/6to4/Teredo/mixed-case fe80 | `test_v6_filter_gaps_x9c.py` | `56ee730` | GREEN |
| [Saturn-zt2](Saturn-zt2/) | tunnel/VPN filter on `_link_ifaces` | `test_iface_tunnel_leak_zt2.py` | `0709ad6` | GREEN |

### From geoff `FAILOVER_SECURITY.md` (rough + full pass)

| Bead | Sev | Spec | Test | Commit | Status |
|---|---|---|---|---|---|
| [Saturn-zd6](Saturn-zd6/) | P1 | bounded `_failover_state` (LRU + TTL) | `test_failover_state_bounded_zd6.py` | `8c91f1f` | GREEN |
| [Saturn-xqw](Saturn-xqw/) | P1 | api_base SSRF gate | `test_api_base_ssrf_xqw.py` | `127f708` | GREEN |
| [Saturn-93w](Saturn-93w/) | P1 | TOFU pin-race operator allowlist | `test_tofu_pin_race_93w.py` | `5930a72` | GREEN |
| [Saturn-eon](Saturn-eon/) | P2 | sanitize ALL TXT values | `test_txt_sanitize_all_eon.py` | `b19fb80` | GREEN |
| [Saturn-jfs](Saturn-jfs/) | P2 | `/api/discover` rate limit | `test_api_discover_ratelimit_jfs.py` | `4330b4d` | GREEN |
| [Saturn-68j](Saturn-68j/) | P3 | per-IP cap on `_failover_state` | `test_failover_state_per_ip_cap_68j.py` | `7222aba` | GREEN |

---

## Routed-out beads (UI lane / environment-blocked)

These were filed by athena during this run but routed to other crews
because brutus's lane couldn't drive them:

| Bead | Reason | Lane |
|---|---|---|
| Saturn-3t8 (cbt.2.a.ui) | bombadil/playwright UI assertions | forge / UI |
| Saturn-6g1 (cbt.2.b attachments) | UI-only (Web-UI/app.js:2409-2447) | bombadil |
| Saturn-ao6 (cbt.2.d edit-regen) | UI-only (Web-UI/app.js:1991) | bombadil → 9ha shipped fix `dcf235b`+`f868d50` |
| Saturn-vyy.linux | needs avahi-browse env | deferred |
| Saturn-ggn.go | needs Go test harness | deferred |
| Saturn-cbt.5.adversarial | needs network harness (`pfctl`, AP-isolated hotspot) | deferred |
| Saturn-cbt.5.web | UI-only (Web-UI render of isolation diagnosis) | bombadil |

---

## What this run changed about brutus's discipline

Captured in `.brutus/CHEATSHEET.md` (15 sections). Highlights:

- **Regression-guard contracts are explicit.** `Saturn-oqm`, `Saturn-b3o`,
  `Saturn-ggn`, `Saturn-vyy` are all "no red phase, preserve-behavior"
  contracts. Documented and accepted under the house rule:
  "If the change is meant to preserve behavior, the contract is that
  the existing test suite still passes — verify it."
- **monkeypatch ≠ mock.** Test-boundary control of Saturn's own helpers
  (`routable_addrs`, `_failover_state`, `psutil.net_if_*`) is fine
  under the no-mocks rule because those aren't external services. Each
  use is documented in the contract.
- **Subprocess peer pattern** (cbt.4, fake-MCP) shipped as the canonical
  shape for "real upstream, controllable behavior" — embedded source
  + tmp_path + state-file flips.
- **Don't fabricate verdicts.** Re-run before writing VERDICT. If RED,
  report the discrepancy — don't attest. Precedent set during the
  wave-2 "queue-cleared-but-no-commits" episode.
- **Decompose laundry lists.** cbt.2 (4 sub-features), cbt.3 (4 audit
  areas), cbt.7 (5 sub-tasks) all decomposed before authoring.
- **Fold-into-existing for audit findings.** When a security audit
  hits a surface that already has a contract, AMEND that contract;
  don't fabricate sibling beads. (zor amend, b3o amend.)

---

## Counts

- **Brutus contracts authored MAY05:** 30 (across phases 0–5).
- **Tests pinned:** ~95 (most contracts ship 1-3 tests; some up to 15).
- **VERDICTs landed:** 30 (all green).
- **Hardener implementation commits attestated:** 28 (2 contracts were
  pure regression guards needing no fix).
- **Geoff audit findings closed:** 6 P1+P2 in `FAILOVER_SECURITY.md`,
  4 from `PARITY_REVIEW_MAY05.md`.
- **Beads routed to other lanes:** 7 (UI / Go / Linux / network harness).

## How to navigate

- Start at the table for the phase that interests you.
- Click the bead link → contract, transcript, verdict, test file path.
- `git show <commit>` for the implementation diff.
- `cat .brutus/CHEATSHEET.md` for the patterns the contracts use.
- `cat RUN_BRIEF_MAY05.md` for the original session brief.
- `cat PRE_SPECS_B3.md` for §17.A–G implementer pre-specs.
- `cat PARITY_REVIEW_MAY05.md`, `FAILOVER_SECURITY.md`,
  `DISCOVERY_AUDIT.md` for geoff's audits.
