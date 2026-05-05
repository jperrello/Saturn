# RUN_NOTES_MAY04 — autonomous promo-push handover

For the human re-entering the loop. Branch: `autonomous/promo-push`. Tip: `29babc9` (mdns-background fold of BONJOUR_AVAHI_FACTS).

## Run scope

Three buckets, executed in parallel by the crew under overseer dispatch. Full pre-spec in `RUN_BRIEF_MAY04.md`; field-level contracts in `PRE_SPECS_B3.md`.

1. **Chat UX (Saturn-qj5.1 – qj5.6)** — clean up the chat tab against real Saturn services and real LLM tokens. Remove the redundant top-right response-style pill (qj5.1), per-chat Settings popup (qj5.2), MCP popup with direct add-server flow (qj5.3), collapse five chat-input fabs into a single `+` menu (qj5.4), retroactive captures (qj5.5), edit-sent-message with truncate-and-regenerate (qj5.6).
2. **Docs/README (Saturn-qj5.8 – qj5.12 + qj5.16.11)** — Diátaxis IA, README rewrite anchored on a hero codeblock, oracle/gullivan/writer pipeline for sourced prose. Outputs: `DOCS_PATTERNS.md` (qj5.9), `README_PATTERNS.md` (qj5.10), README rewrite (qj5.11), docs/ tree split (qj5.12), admin-auth doc drift fix (qj5.16.11).
3. **Config-proof + security (Saturn-qj5.13 – qj5.15 + the qj5.16 audit chain)** — `CONFIG_FIELDS.md` schema lift (qj5.13), boot validators that refuse-on-unsafe (qj5.14), per-turn config receipt patterns (qj5.15), and the full `SECURITY_AUDIT.md` §1–§17 chain (qj5.16) closing F-1 through F-9 plus the structural items (TLS, mDNS hijack, beacon ephemeral_key, TOFU node_id, sleep-proxy semantics).

~125 commits on the branch since fork from `main`; ~60 directly tagged with bead IDs above. Full canonical list: `git log --oneline main..autonomous/promo-push`.

## What shipped — by bucket

### Bucket 1: Chat UX

- `6461641` qj5.1 — remove top-right response-style pill (lived inside Chat already)
- `c2845b4` qj5.2 — per-chat Settings popup (style/model/service)
- `60a589b` qj5.3 — MCP popup with visible label + direct Add-MCP-server flow
- `ba2f925` qj5.4 — collapse five chat-input fabs into single `+` menu
- `74c98aa` qj5.{2,3,4,6} — retroactive showboat captures (qj5.5)
- `a232b13` qj5.6 — edit-sent-message affordance with truncate-and-regenerate

### Bucket 2: Docs/README

- `c8c26d6` / `00074d2` qj5.9 — DOCS_PATTERNS.md (rough → full)
- `8df63bd` / `b10037e` qj5.10 — README_PATTERNS.md (initial → expanded sources)
- `ebe38bd` / `eb62844` qj5.11 — README rewrite (rough → full prose pass with oracle answers + SECURITY_AUDIT lifts)
- `5ff8c1a` qj5.12 — Diátaxis IA, five mandatory pages, file moves
- `92cbabf` qj5.{11,12,16.11} — admin-auth doc drift, http-api split, README polish
- `b130c6d` `docs/admin/security.md` — operational translation of SECURITY_AUDIT
- `a773708` `docs/admin/configure.md` — 8-group Configure runbook + per-service editor
- `29babc9` `docs/concepts/mdns-background.md` — folded BONJOUR_AVAHI_FACTS (gullivan `ca8dae1` + `e6f7627`): SPS DNS Update sourcing, Bonjour/Avahi field gotchas

### Bucket 3: Config-proof + security

- `4200c1b` qj5.16 — `SECURITY_AUDIT.md` + nine sub-beads filed
- `4506373` qj5.13 — `CONFIG_FIELDS.md` admin schema + validators
- `38962eb` qj5.13/.14/.15 — `PRE_SPECS_B3.md` B3 implementation contracts
- `8b1e54d` qj5.13 commit 1 + qj5.16.13.{1,2} — `AdminConfig` schema lift, `TrustRebindError`, `reclassify` wiring
- `70f7beb` qj5.13 commit 2 (Saturn-hft v2) — admin Configure page server-renders 8-group schema with inline values
- `b38b4af` qj5.13 commit 3 (Saturn-6sb) — per-service editor on Configure page
- `26d20e1` qj5.14 — boot validators (C.1.1–C.1.8) + LLM-honoured chat path
- `437ee7b` qj5.13.{4,6} + qj5.14.1 — drift guard + SSR pre-fill for select/checkbox + OpenRouter env plumb
- `19b3a28` / `c0453a0` qj5.14 — `CONFIG_PROOF_PATTERNS.md` (rough → full)
- `69ea76d` / `427bb12` qj5.15 — `CONFIG_RECEIPT_PATTERNS.md` (rough → full)
- `150468c` qj5.16.13 — TOFU `node_id` pinning + admin allowlist
- `20fe48a` qj5.16.13 — §15 implementer pre-spec for node_id TOFU
- `8f35d3a` qj5.16.14 — §17.E sleep-transition + power-mgmt opt-in pre-spec
- `fbb5896` qj5.16.1 — bearer-token auth on `/v1/*`, default bind `127.0.0.1`
- `370f9fa` qj5.16.2 — bearer-token admin auth on `/api/{services,admin,system,mcp}/*`
- `4227474` qj5.8v5 — unify auth via `build_app()`, close `server.module` bypass
- `a8b02c2` qj5.16.{5,6} — F-9 closed-by-schema; F-5 deletion fix
- `8bf0ef6` qj5.16.{6,7} — remove proxy body/query keys + sanitise upstream-leak surfaces
- `e5157fc` qj5.16.7 — `/api/proxy/models` query-string key + leak-channel matrix audit
- `c87ec3d` qj5.16.8 — TLS posture, threats, today/tomorrow mitigations
- `5e65912` qj5.16.9 — mDNS priority hijack closes structural bucket
- `7ae4d07` / `3345dbb` qj5.16.10 — `/api/usage` user_id bypass audit + admin-gate fix; stop honouring untrusted XFF
- `75dd610` qj5.16/§16 — Bonjour SPS freezes TXT (beacon platform notes)
- `20fe48a` qj5.16.3 — XFF trust boundary trace + drop-in fix
- `a3fb68a` qj5.16.4 — beacon `ephemeral_key` lifecycle deep-dive

## Open follow-ups

### In flight (`bd list --state in_progress`)

- **Saturn-qj5.13.7** — `/admin/configure` regression: SSR route lost `Depends(require_admin)` between commits 2 and 3. Page leaks admin posture (CIDRs, route policy, env-var *names*, trust mode) to any LAN peer. Secret values do not traverse this path — env-var names only — but it reverts the F-4 closure shape. Restore `Depends(require_admin)` on `admin_configure_route` and the `/configure` and `/admin/services` aliases. Add a no-bearer regression test (`c9347a0` already scaffolds this).
- **Saturn-qj5.16.14** — Beacon sleep-transition unregister + power-mgmt opt-in. Pre-spec drafted in PRE_SPECS_B3.md §17.E. Co-land with §7.5 beacon-budget plumbing — both touch `run_beacon`. New module `saturn/mdns/sleep.py` (KeepAwake + SleepWatcher); six tests; first-run CLI prompt + Configure-page row.
- **Saturn-qj5.16.3** — F-3: XFF trusted unconditionally. Audit landed (`20fe48a`); fix in flight via `_set_trusted_proxies` + the A.3 Configure-page control. Cross-test in qj5.13.3 (P3) wires the runtime apply path.
- **Saturn-qj5.16.13.3** — `SettleDetector` integration in TOFU pin to close the §15.2.b race.
- **Saturn-7j3** — known-nodes Configure-page UI (qj5.16.13 commit-3). Scaffold in `2ed5252`; pick-from-known-nodes control on the A.8 row.
- **Saturn-qj5.15** — Chat UI live receipt of resolved per-turn config (token cap, temp, model, system). Patterns landed in `CONFIG_RECEIPT_PATTERNS.md`; UI surface still pending.
- **Saturn-gww.3** — Web-UI Nielsen heuristics fixes (full pass). Audit in `HEURISTICS_AUDIT.md`. The closure sweep should reconcile the open `gww.4.x` children as part of landing this.

### P3 backlog (`bd list --state open --priority 3`)

- **qj5.13.2** — Restart-preservation parametrize is single-field; expand per `PRE_SPECS_B3.md` §17.A.4.2.
- **qj5.13.3** — Cross-contract test: `trust_mode` flip via `/api/admin/config` affects routing (§15).
- **qj5.13.5** — `test_chat_index_html_does_not_carry_admin_schema_ids` checks wrong prefix.
- **qj5.13.9** — Docs drift: connector-label rename "API Key" → "Bearer Token" not reflected everywhere.
- **qj5.14.4** — `SATURN_DEV_MODE` per-check overrides + boot banner + C.1.8 asymmetry.
- **qj5.16.13.4** — `_reclassify_discovered()` synthesises a minimal `SaturnService`; fragile if `_classify` shape evolves.
- **qj5.16.15** — Dead-code cleanup: `TrustRebindError` unused after `8b1e54d`.

### Tail items

- `gww.3` closure sweep — reconcile `gww.4.x` open children before closing parent.
- Bucket-2 docs follow-on: `docs/admin/platform-notes.md` (Windows BPS, iOS `NSBonjourServices`, Android `NsdManager`) — facts #9, #10 from BONJOUR_AVAHI_FACTS not yet folded; would fit alongside `docs/admin/security.md` and `docs/admin/configure.md`.

## Architectural decisions worth carrying forward

- **CONFIG_FIELDS schema as the single contract.** Every admin-tunable setting has one row in `CONFIG_FIELDS.md` (§A server-wide, §B per-service, §C boot rules). Server-side `AdminConfig` (`saturn/web.py`), the `/api/admin/config` round-trip, the Configure-page UI, and the boot validators all derive from that schema — none of them re-declare it. New settings ship by adding the §A row, the field on `AdminConfig`, the `_check_*` helper for §C, the UI control, and four tests (round-trip, persist, live-apply, refuse-on-invalid). PRE_SPECS_B3.md §17.A.4 frames the test invariants.
- **TOFU `node_id` pinning** (§15, qj5.16.13). Trust is keyed on a stable per-node UUIDv4, not on hostname or `priority`. `trust_mode` is `tofu` (default), `allowlist`, or `open` (rejected outside `SATURN_DEV_MODE`). The TXT record carries the `node_id`; first-seen pins it; mismatches surface as `TrustRebindError` and land in the pending-rejections table on the Configure A.8 group.
- **Dual-entry-point Configure page.** `/admin/configure` renders standalone with server-side pre-fill (the SPA tab is the same page). Bookmarkable, deep-linkable from runbooks. Authentication is the same `Depends(require_admin)` gate as the JSON API — see qj5.13.7 above for the regression that proves the gate is load-bearing.
- **Bearer-fetch override pattern.** Web-UI `fetch` is wrapped to attach the admin bearer from the resolved `admin_token_env` automatically; server-side `require_admin` accepts either the cookie session (Web-UI) or a bearer header (curl, scripts). The same pattern applies on `/v1/*` against `runner_token_env`. This is what made `4227474` (`build_app()` unifies auth) possible without forking SPA vs. CLI auth flows.
- **Harness as evergreen verification backbone.** The Bombadil + showboat harness shipped early in the run (`f195dbd`, `c4f9a19`) and was reused by every subsequent bucket: chat-UX captures, boot-validator violation matrix (`b75305f`), no-bearer regression (`c9347a0`), per-service editor (`bb3d259`). New features ship with a real-Saturn harness pass — no mocked discovery, no mocked LLM. Pattern is durable; reuse rather than rewrite.
- **CONFIG_RECEIPT + CONFIG_PROOF as paired patterns.** `CONFIG_PROOF_PATTERNS.md` (qj5.14) tests that the LLM honours requested params end-to-end (max_tokens, temperature, model ID, system prompt, stop). `CONFIG_RECEIPT_PATTERNS.md` (qj5.15) is the user-facing receipt — what params actually applied to *this* turn — surfaced in the Chat UI. Same fields, two angles: server-side proof + client-side receipt.

## Pointer index

Repo-root anchors. Every section in this file points to one of these for the structured detail.

| File | Purpose |
|---|---|
| `RUN_BRIEF_MAY04.md` | This run's pre-spec. Three buckets, dispatch order, success criteria. |
| `PRE_SPECS_B3.md` | Field-level implementation contracts for qj5.13 / qj5.14 / qj5.15 / qj5.16.14. |
| `CONFIG_FIELDS.md` | Schema reference. §A server-wide, §B per-service, §C boot rules. |
| `CONFIG_PROOF_PATTERNS.md` | qj5.14 — server-side proof that LLMs honour requested params. |
| `CONFIG_RECEIPT_PATTERNS.md` | qj5.15 — client-side receipt of applied per-turn config. |
| `SECURITY_AUDIT.md` | qj5.16 — F-1…F-9 + structural items + §15 (TOFU) + §16 (SPS) + §17 power-mgmt. |
| `BONJOUR_AVAHI_FACTS.md` | gullivan's research: 10 gaps, sourced. SPS DNS Update format, RFC 6763 §6.2 tiers, conflict suffix differences, BPS v2.0.2, iOS/Android API gates. |
| `DOCS_PATTERNS.md` | qj5.9 — Diátaxis IA + the five mandatory pages. |
| `README_PATTERNS.md` | qj5.10 — README rewrite framework: hero codeblock, promise tagline, sourced claims. |
| `HEURISTICS_AUDIT.md` | gww.2 — Nielsen pass on Web-UI; gww.3 fixes drive from this. |
| `FEATURE_INVENTORY.md` | gww — feature surface inventory (basis for gww.4 pick-one decisions). |

## Suggested re-entry prompt

> Resume `autonomous/promo-push`. Open in-flight beads: qj5.13.7 (restore `Depends(require_admin)` on `/admin/configure`), qj5.16.14 (sleep-transition + power-mgmt opt-in, co-land with §7.5), qj5.16.3 (XFF trust fix wiring), qj5.16.13.3 (SettleDetector in TOFU pin), Saturn-7j3 (known-nodes UI), qj5.15 (Chat UI receipt surface), gww.3 (heuristics fixes + closure sweep). Start with `bd ready`. Patterns: `PRE_SPECS_B3.md` for contracts, `CONFIG_FIELDS.md` for schema, `RUN_NOTES_MAY04.md` for the handover summary.
