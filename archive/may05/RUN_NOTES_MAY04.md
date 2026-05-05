# RUN_NOTES_MAY04 — autonomous promo-push handover

For the human re-entering the loop. Branch: `autonomous/promo-push`. Tip at land: `50750fe` (qj5.16.14 beacon sleep-transition + power-mgmt + §7.5 budget plumbing).

## What shipped this run — one paragraph

Three parallel buckets, ~140 commits since fork from `main`, ~75 directly tagged with bead IDs. **Bucket 1 (chat UX)** cleaned the chat tab into a single textarea + `+` menu + send: removed the redundant top-right style pill, added a per-chat Settings popup, an MCP popup with direct add-server flow, edit-sent-message with truncate-and-regenerate. **Bucket 2 (docs)** rewrote the README on top of `README_PATTERNS.md`, restructured `docs/` to a Diátaxis IA, shipped four admin runbooks (`docs/admin/security.md`, `configure.md`, `platform-notes.md`) and a deep mDNS background page now sourced against gullivan's `BONJOUR_AVAHI_FACTS.md`. **Bucket 3 (config-proof + security)** lifted the eight-group `AdminConfig` schema into `CONFIG_FIELDS.md`, shipped a Configure page that server-renders that schema with inline values + per-service editor, wired boot validators (C.1.1–C.1.8) that refuse-on-unsafe, landed bearer-token auth across `/v1/*` and `/api/{services,admin,system,mcp}/*`, closed F-1 through F-9 in `SECURITY_AUDIT.md`, pinned trust on TOFU `node_id`, surfaced per-turn config as a `saturn_meta` receipt envelope, and shipped beacon sleep-transition unregister + power-mgmt opt-in. The Saturn that lands at `50750fe` refuses to start with insecure config, refuses to expose admin endpoints without auth, refuses to leak admin posture via the Configure SSR route, refuses to honour untrusted `X-Forwarded-For`, and refuses to keep a stale beacon TXT alive past sleep.

## Run scope

Three buckets, executed in parallel by the crew under overseer dispatch. Full pre-spec in `RUN_BRIEF_MAY04.md`; field-level contracts in `PRE_SPECS_B3.md`.

1. **Chat UX (Saturn-qj5.1 – qj5.6)** — clean up the chat tab against real Saturn services and real LLM tokens.
2. **Docs/README (Saturn-qj5.8 – qj5.12 + qj5.16.11)** — Diátaxis IA, README rewrite, oracle/gullivan/writer pipeline.
3. **Config-proof + security (Saturn-qj5.13 – qj5.15 + the qj5.16 audit chain)** — `CONFIG_FIELDS` schema lift, boot validators, per-turn receipt patterns, the full `SECURITY_AUDIT.md` chain.

Full canonical commit list: `git log --oneline main..autonomous/promo-push`.

## What shipped — by bucket

### Bucket 1: Chat UX

- `6461641` qj5.1 — remove top-right response-style pill
- `c2845b4` qj5.2 — per-chat Settings popup (style/model/service)
- `60a589b` qj5.3 — MCP popup with visible label + direct Add-MCP-server flow
- `ba2f925` qj5.4 — collapse five chat-input fabs into single `+` menu
- `74c98aa` qj5.5 — retroactive showboat captures
- `a232b13` qj5.6 — edit-sent-message affordance with truncate-and-regenerate

### Bucket 2: Docs/README

- `c8c26d6` / `00074d2` qj5.9 — `DOCS_PATTERNS.md`
- `8df63bd` / `b10037e` qj5.10 — `README_PATTERNS.md`
- `ebe38bd` / `eb62844` qj5.11 — README rewrite (oracle answers + SECURITY_AUDIT lifts)
- `5ff8c1a` qj5.12 — Diátaxis IA, five mandatory pages, file moves
- `92cbabf` qj5.{11,12,16.11} — admin-auth doc drift, http-api split, README polish
- `b130c6d` `docs/admin/security.md` — operational translation of SECURITY_AUDIT
- `a773708` `docs/admin/configure.md` — 8-group Configure runbook + per-service editor
- `a01ee41` `docs/admin/platform-notes.md` — per-OS browseability, BPS, iOS NSBonjourServices, AP isolation
- `29babc9` `docs/concepts/mdns-background.md` — fold of `BONJOUR_AVAHI_FACTS.md` (gullivan `ca8dae1` + `e6f7627`): SPS DNS Update sourcing + Bonjour/Avahi field gotchas

### Bucket 3: Config-proof + security

- `4200c1b` qj5.16 — `SECURITY_AUDIT.md` + nine sub-beads filed
- `4506373` qj5.13 — `CONFIG_FIELDS.md` admin schema + validators
- `38962eb` qj5.13/.14/.15 — `PRE_SPECS_B3.md` B3 implementation contracts
- `8b1e54d` qj5.13 commit 1 + qj5.16.13.{1,2} — `AdminConfig` schema lift, `TrustRebindError`, `reclassify` wiring
- `70f7beb` qj5.13 commit 2 (Saturn-hft v2) — Configure page server-renders 8-group schema
- `b38b4af` qj5.13 commit 3 (Saturn-6sb) — per-service editor on Configure page
- `3a27eeb` qj5.13.7 — restore `Depends(require_admin)` on `/admin/configure` (SSR-leak fix)
- `f582af7` qj5.13.7 demo — post-fix capture; SSR leak gated, regression guard green
- `ebe57f8` Saturn-7j3 — known-nodes UI on Configure page (qj5.16.13 commit-3)
- `9325c5e` Saturn-7j3 demo — 4-surface audit GREEN
- `26d20e1` qj5.14 — boot validators (C.1.1–C.1.8) + LLM-honoured chat path
- `437ee7b` qj5.13.{4,6} + qj5.14.1 — drift guard + SSR pre-fill + OpenRouter env plumb
- `19b3a28` / `c0453a0` qj5.14 — `CONFIG_PROOF_PATTERNS.md`
- `69ea76d` / `427bb12` qj5.15 — `CONFIG_RECEIPT_PATTERNS.md`
- `3de812c` qj5.15 — `saturn_meta` receipt envelope on `/api/chat`
- `f106fee` qj5.15 demo — saturn_meta envelope GREEN
- `375c616` qj5.15.2 — §17.F lift `saturn_meta` to other 3 chat surfaces (specs)
- `150468c` qj5.16.13 — TOFU `node_id` pinning + admin allowlist
- `20fe48a` qj5.16.13 — §15 implementer pre-spec for node_id TOFU
- `8f35d3a` qj5.16.14 — §17.E sleep-transition + power-mgmt opt-in pre-spec
- `50750fe` qj5.16.14 — beacon sleep-transition + power-mgmt opt-in + §7.5 budget plumbing
- `fbb5896` qj5.16.1 — bearer-token auth on `/v1/*`, default bind `127.0.0.1`
- `370f9fa` qj5.16.2 — bearer-token admin auth on `/api/{services,admin,system,mcp}/*`
- `4227474` qj5.8v5 — unify auth via `build_app()`, close `server.module` bypass
- `c8d0b4e` qj5.16.3 + Saturn-n5h — `trusted_proxies` allowlist + `forwarded_allow_ips=[]` + admin bearer-fetch wrapper
- `9d75f13` qj5.16.3 demo — XFF spoof gate GREEN
- `a8b02c2` qj5.16.{5,6} — F-9 closed-by-schema; F-5 deletion fix
- `8bf0ef6` qj5.16.{6,7} — remove proxy body/query keys + sanitise upstream-leak surfaces
- `e5157fc` qj5.16.7 — `/api/proxy/models` query-string key + leak-channel matrix audit
- `c87ec3d` qj5.16.8 — TLS posture, threats, today/tomorrow mitigations
- `5e65912` qj5.16.9 — mDNS priority hijack closes structural bucket
- `7ae4d07` / `3345dbb` qj5.16.10 — `/api/usage` user_id bypass audit + admin-gate fix
- `75dd610` qj5.16/§16 — Bonjour SPS freezes TXT (beacon platform notes)
- `a3fb68a` qj5.16.4 — beacon `ephemeral_key` lifecycle deep-dive
- `db74a14` gww.3 — heuristics closure pass appended to `HEURISTICS_AUDIT.md`
- `71f8115` `FINAL_AUDIT_SUMMARY.md` — handover index (geoff)

## Bead status

### Closed this run (29 promo-push, 25 run-may04 epic + sub-beads)

Chat UX: `qj5.1`, `qj5.2`, `qj5.3`, `qj5.4`, `qj5.6`, `qj5.7`. Docs: `qj5.11`. Config + security: `qj5.13`, `qj5.13.7`, `Saturn-hft`, `Saturn-6sb`, `Saturn-7j3`, `qj5.14`, `qj5.14.1`, `qj5.15`, `qj5.16`, `qj5.16.1`, `qj5.16.2`, `qj5.16.3`, `qj5.16.4`, `qj5.16.5`, `qj5.16.10`, `qj5.16.13`, `qj5.16.13.1`, `qj5.16.13.2`, `qj5.16.14`, `Saturn-n5h`. Plus the `gww.3` heuristics-fixes parent (closed via implicit-closure pass — `db74a14`).

Run all: `bd list --state closed --json | jq '.[] | select(.labels | index("promo-push"))'`.

### Remaining open — cleanup batch (12 beads)

These are P2/P3 follow-ups landed against shipped work; none block the run from landing. Pick up against `bd ready` next session.

**P2 (six):**

- `qj5.13.8` — Configure-page poll loops have no `document.visibilityState` gate (idle tab burns RPM).
- `qj5.13.10` — Promote `qj5.13.7` no-bearer probe from demo script to pytest assertion.
- `qj5.14.2` — `bind_host` validator vs CLI-default disagreement (qj5.14 vs CONFIG_FIELDS A.3).
- `qj5.14.3` — Boot validator helpers duplicated in `saturn/web.py` + `saturn/boot_validators.py`.
- `qj5.15.1` — `saturn_meta` diff missing `match[]` + `ignored[]` arrays (qj5.15 §17.C.1 partial).
- `qj5.16.13.5` — "Use in allowlist" click silently no-ops when `trust_mode != allowlist` (Saturn-7j3).

**P3 (six):**

- `qj5.13.5` — `test_chat_index_html_does_not_carry_admin_schema_ids` checks wrong prefix.
- `qj5.13.9` — Docs drift: connector-label rename "API Key" → "Bearer Token" not reflected in docs/.
- `qj5.14.4` — `SATURN_DEV_MODE` per-check overrides + boot banner + C.1.8 asymmetry.
- `qj5.15.3` — Document Pattern 3 provenance upgrade path on `saturn/receipt.py` (qj5.15 §17.C.3).
- `qj5.16.13.4` — `_reclassify_discovered()` synthesises minimal `SaturnService` — fragile if `_classify_trust` grows.
- `qj5.16.15` — Dead-code cleanup: `TrustRebindError` class unused after `8b1e54d`.

A separate parallel sweep against the residual heuristics items (gww.3 closure pass) suggested splitting that work into `gww.5` – `gww.10` clusters before re-opening — see `HEURISTICS_AUDIT.md` §Closure pass.

## Architectural decisions worth carrying forward

- **`CONFIG_FIELDS` schema as the single contract.** Every admin-tunable setting has one row in `CONFIG_FIELDS.md` (§A server-wide, §B per-service, §C boot rules). Server-side `AdminConfig`, the `/api/admin/config` round-trip, the Configure-page UI, and the boot validators all derive from that schema — none re-declare it. New settings ship by adding the §A row, the field on `AdminConfig`, the `_check_*` helper for §C, the UI control, and four tests (round-trip, persist, live-apply, refuse-on-invalid). PRE_SPECS_B3.md §17.A.4 frames the test invariants.
- **TOFU `node_id` pinning** (§15, qj5.16.13). Trust is keyed on a stable per-node UUIDv4, not on hostname or `priority`. `trust_mode` is `tofu` (default), `allowlist`, or `open` (rejected outside `SATURN_DEV_MODE`). The TXT record carries the `node_id`; first-seen pins it; mismatches surface as `TrustRebindError` and land in the pending-rejections table on Configure A.8.
- **Dual-entry-point Configure page.** `/admin/configure` renders standalone with server-side pre-fill (the SPA tab is the same page). Bookmarkable, deep-linkable. Authentication is the same `Depends(require_admin)` gate as the JSON API — qj5.13.7 was the regression that proved the gate is load-bearing.
- **Bearer-fetch override pattern** (`c8d0b4e`, `4227474`). Web-UI `fetch` is wrapped to attach the admin bearer from the resolved `admin_token_env` automatically; server-side `require_admin` accepts cookie session OR bearer header. Same shape on `/v1/*` against `runner_token_env`. This is what made the `build_app()` auth unification possible without forking SPA vs CLI flows.
- **Harness as evergreen verification backbone.** Bombadil + showboat shipped early (`f195dbd`, `c4f9a19`) and was reused by every subsequent bucket: chat-UX captures, boot-validator violation matrix (`b75305f`), no-bearer regression (`f582af7`), per-service editor, saturn_meta envelope (`f106fee`), XFF spoof gate (`9d75f13`), Saturn-7j3 (`9325c5e`). Real-Saturn passes — no mocked discovery, no mocked LLM. Reuse rather than rewrite.
- **CONFIG_RECEIPT + CONFIG_PROOF as paired patterns.** `CONFIG_PROOF_PATTERNS.md` (qj5.14) tests that the LLM honours requested params end-to-end (max_tokens, temperature, model ID, system prompt, stop). `CONFIG_RECEIPT_PATTERNS.md` (qj5.15) is the user-facing receipt — what params actually applied to *this* turn — surfaced via the `saturn_meta` envelope (`3de812c`). Same fields, two angles: server-side proof + client-side receipt.

## Pointer index

Repo-root anchors. Every section in this file points to one of these for the structured detail.

| File | Purpose |
|---|---|
| `RUN_BRIEF_MAY04.md` | This run's pre-spec. Three buckets, dispatch order, success criteria. |
| `PRE_SPECS_B3.md` | Field-level implementation contracts for qj5.13 / qj5.14 / qj5.15 / qj5.16.14. |
| `FINAL_AUDIT_SUMMARY.md` | **geoff's handover index** (`71f8115`). Audit-side recap of what closed against `SECURITY_AUDIT.md`. |
| `FINAL_VERDICT.md` | **brutus's verdict** (in flight at land). Pass/fail across the run's ship-bar invariants. |
| `LANDING_DEMO.md` | **demo's landing capture** (in flight at land). End-state showboat against the shipped surface. |
| `CONFIG_FIELDS.md` | Schema reference. §A server-wide, §B per-service, §C boot rules. |
| `CONFIG_PROOF_PATTERNS.md` | qj5.14 — server-side proof that LLMs honour requested params. |
| `CONFIG_RECEIPT_PATTERNS.md` | qj5.15 — client-side receipt of applied per-turn config (`saturn_meta`). |
| `SECURITY_AUDIT.md` | qj5.16 — F-1…F-9 + structural items + §15 (TOFU) + §16 (SPS) + §17 power-mgmt. |
| `BONJOUR_AVAHI_FACTS.md` | gullivan's research: 10 gaps, sourced. |
| `DOCS_PATTERNS.md` | qj5.9 — Diátaxis IA + the five mandatory pages. |
| `README_PATTERNS.md` | qj5.10 — README rewrite framework. |
| `HEURISTICS_AUDIT.md` | gww.2 audit + gww.3 closure pass appended. |
| `FEATURE_INVENTORY.md` | gww — feature surface inventory. |

## Suggested re-entry prompt

> Resume `autonomous/promo-push`. Branch tip: `50750fe`. Run is landed. Open follow-ups are P2/P3 cleanup only — no blockers. Start with `bd ready`; six P2s and six P3s are mapped in `RUN_NOTES_MAY04.md` §Remaining open. For audit-side recap read `FINAL_AUDIT_SUMMARY.md`; for the verdict and the landing demo read `FINAL_VERDICT.md` and `LANDING_DEMO.md`. Patterns: `PRE_SPECS_B3.md` for contracts, `CONFIG_FIELDS.md` for schema. If new heuristics work is on the table, the residual map and the suggested `gww.5–gww.10` cluster split lives in `HEURISTICS_AUDIT.md` §Closure pass.
