# Saturn Promo-Push Audit — Final Summary

> Handover catalogue of geoff's audit work on the
> `autonomous/promo-push` branch, 2026-05-04.
>
> Live deliverables: `SECURITY_AUDIT.md` (16 §-sections),
> `PRE_SPECS_B3.md` (6 §-sections), `CONFIG_FIELDS.md` (admin schema).
> Companion docs: `CONFIG_RECEIPT_PATTERNS.md` (gullivan, qj5.15
> research), writer's `docs/admin/configure.md` (admin runbook).
>
> This file is the index — read it first when re-entering the audit
> trail; jump from here into the specific section/bead.

---

## 1. SECURITY_AUDIT.md — section index

Sixteen sections across two passes. §1–6 are the original structural
sweep; §7–14 deep-dive each finding; §15–16 are implementer pre-specs
co-located with the audit they implement.

| § | Topic | Bead | Status |
|---|---|---|---|
| 1 | TXT-record exposure surface | — | descriptive |
| 2 | API-key flow end-to-end | — | descriptive |
| 3 | Llama (Ollama) endpoint verification | — | live-tested |
| 4 | Multi-tenant LAN threat model | — | descriptive |
| 5 | Findings disposition (F-1 … F-9) | — | filed nine sub-beads |
| 6 | Recommended config-field expansion | — | bridges to CONFIG_FIELDS.md |
| 7 | Beacon ephemeral-key lifecycle deep-dive | qj5.16.4 (closed) | F-2 |
| 8 | X-Forwarded-For trust boundary | qj5.16.3 (closed) | F-3 |
| 9 | `/api/usage` `user_id` query bypass | qj5.16.10 (closed) | F-3 sub |
| 10 | F-9 disposition (closed-by-schema) | qj5.16.5 (closed) | F-9 |
| 11 | `/api/proxy/chat` body `api_key` | qj5.16.6 (closed) | F-5 |
| 12 | `/api/proxy/models` query-string `api_key` | qj5.16.7 (closed) | F-6 |
| 13 | No TLS posture | qj5.16.8 (closed) | F-7 |
| 14 | mDNS priority hijack | qj5.16.9 (closed) | F-8 |
| 15 | qj5.16.13 implementer pre-spec (TOFU) | qj5.16.13 (closed) | impl |
| 16 | Beacon platform notes — Bonjour SPS | qj5.16.14 (open) | impl |

The audit closes nine F-thread findings (F-1 through F-9), plus a
sub-finding on usage. Implementer-side wiring for §15 (TOFU)
shipped; §16 (sleep-transition) is hardener's current bead.

## 2. PRE_SPECS_B3.md — section index

Six implementer pre-specs in PRE_SPECS_B3.md, all in the §17.* family
to keep them logically separate from the audit.

| § | Bead | Topic | Implementer status |
|---|---|---|---|
| 17.A | qj5.13 | Configure page schema lift (8 groups, 22 fields) | shipped (commit-1 + commit-2 + commit-3) |
| 17.B | qj5.14 | Boot validators (C.1.1–C.1.8) + LLM-honoured tests | shipped |
| 17.C | qj5.15 | Per-turn `saturn_meta` receipt | shipped on `/api/chat` |
| 17.D | — | Cross-bead landing order | — |
| 17.E | qj5.16.14 | Beacon sleep-transition + power-mgmt opt-in | hardener current bead |
| 17.F | qj5.15.2 | Lift `saturn_meta` to other 3 chat surfaces | hardener pending |

## 3. Bead inventory by family

### 3.1 Audit family — Saturn-qj5.16.*

**Original F-thread closures (filed 2026-05-04):**

| Bead | Pri | Status | Topic | Notes |
|------|---|---|---|---|
| qj5.16.1 | P0 | closed | F-1 runner `/v1/*` unauth | brutus auth wiring |
| qj5.16.2 | P0 | closed | F-4 admin endpoints unauth | brutus auth wiring |
| qj5.16.3 | P1 | closed | F-3 XFF rate-limit bypass | §8 |
| qj5.16.4 | P1 | closed | F-2 beacon TXT scope | §7 |
| qj5.16.5 | P1 | closed | F-9 default password | §10, closed-by-schema |
| qj5.16.6 | P2 | closed | F-5 `/api/proxy/chat` body key | §11 |
| qj5.16.7 | P2 | closed | F-6 `/api/proxy/models` query key | §12 |
| qj5.16.8 | P2 | closed | F-7 no TLS posture | §13 |
| qj5.16.9 | P2 | closed | F-8 mDNS priority hijack | §14 |

**Sub-findings + impl beads (filed during deep-dives):**

| Bead | Pri | Status | Topic |
|------|---|---|---|
| qj5.16.10 | P1 | closed | F-3 sub: `/api/usage` `user_id` bypass |
| qj5.16.11 | P2 | closed | docs ADMIN_PASSWORD (post-A.2) |
| qj5.16.12 | P2 | open | TLS auto-cert UX (post-A.3 wiring) |
| qj5.16.13 | P1 | closed | TOFU + allowlist (impl bead) |
| qj5.16.13.1 | P1 | closed | TrustRebindError wiring (review-found) |
| qj5.16.13.2 | P1 | closed | `reclassify_all` wiring (review-found) |
| qj5.16.13.3 | P2 | in_progress | SettleDetector race in TOFU pin |
| qj5.16.13.4 | P3 | open | `_reclassify_discovered` fragility |
| qj5.16.13.5 | P2 | open | "Use in allowlist" no-op when not in allowlist mode |
| qj5.16.14 | P1 | in_progress | Beacon sleep-transition + power-mgmt opt-in |
| qj5.16.15 | P3 | open | Dead-code cleanup: `TrustRebindError` class |

### 3.2 B3 implementation family

**qj5.13 (Configure page) follow-ups:**

| Bead | Pri | Status | Topic |
|------|---|---|---|
| qj5.13.1 | P2 | open | Live-propagation tests cover only `rate_rpm` |
| qj5.13.2 | P3 | open | Restart-preservation parametrize is single-field |
| qj5.13.3 | P3 | open | Cross-contract test: `trust_mode` flip → routing |
| qj5.13.4 | P2 | closed | Drift guard: AdminConfig ↔ AC_FIELDS meta-test |
| qj5.13.5 | P3 | open | `test_chat_index_html_does_not_carry...` wrong prefix |
| qj5.13.6 | P2 | closed | SSR pre-fill missing for checkbox + select |
| qj5.13.7 | P1 | closed | `/admin/configure` lost auth (commit-3 regression) |
| qj5.13.8 | P2 | open | Configure-page polls have no `visibilityState` gate |
| qj5.13.9 | P3 | open | "Bearer Token" rename docs drift |
| qj5.13.10 | P2 | open | Promote no-bearer probe to pytest assertion |

**qj5.14 (boot validators) follow-ups:**

| Bead | Pri | Status | Topic |
|------|---|---|---|
| qj5.14.1 | P1 | closed | OpenRouter sub-key not plumbed to subprocess |
| qj5.14.2 | P2 | open | `bind_host` validator vs CLI-default disagreement |
| qj5.14.3 | P2 | open | Boot validator helpers duplicated web.py + boot_validators.py |
| qj5.14.4 | P3 | open | `SATURN_DEV_MODE` ergonomics + C.1.8 asymmetry |

**qj5.15 (receipt) follow-ups:**

| Bead | Pri | Status | Topic |
|------|---|---|---|
| qj5.15.1 | P2 | open | `saturn_meta.diff` missing `match[]` + `ignored[]` |
| qj5.15.2 | P2 | in_progress | `saturn_meta` only on `/api/chat` (3 surfaces missing); §17.F pre-spec ready |
| qj5.15.3 | P3 | open | Document Pattern 3 provenance upgrade path |

### 3.3 Standalone

| Bead | Pri | Status | Topic |
|------|---|---|---|
| Saturn-n5h | P1 | open | SPA admin bearer-fetch wrapper missing (citation: Web-UI/app.js + index.html + server.ts grep, all zero matches) |

## 4. Bead totals

| State | Count |
|---|---|
| Closed | 14 |
| Open (incl. in_progress) | 18 |
| **Total filed during run** | **32** |

P0/P1 outcomes: every named structural finding (F-1 … F-9 plus the
discovered F-3 sub) closed; remaining P1s are implementer beads
(qj5.16.14 sleep-transition, Saturn-n5h bearer-fetch, qj5.16.13.3
settle-pin race in_progress).

## 5. Outstanding hardener queue (post-run)

In rough priority order:

1. **Saturn-n5h (P1)** — wire SPA bearer-fetch override or session
   cookie path in `require_admin`. Without this, the entire admin SPA
   silently 401s outside playwright `page.route()` injection.
2. **qj5.16.14 (P1, in_progress)** — beacon sleep-transition +
   power-mgmt opt-in. Pre-spec: §17.E. Co-landable with qj5.16.4
   beacon-budget plumbing.
3. **qj5.16.13.3 (P2, in_progress)** — SettleDetector race in TOFU
   pin (silent first-contact race window).
4. **qj5.15.2 (P2, in_progress)** — lift `saturn_meta` to the other
   three chat surfaces. Pre-spec: §17.F. ≈45 LOC + 100 LOC tests.
5. **qj5.13.7 residual + qj5.13.8** — promote no-bearer probe to
   pytest body-negative-assertion; add `visibilityState` gate to
   the two poll loops. Both small.
6. **qj5.13.1 + qj5.15.1** — broaden test coverage and emit `match`
   / `ignored` diff buckets respectively. Both schema-tolerant
   additions, no breaking change.
7. **qj5.14.2 / .14.3 / .14.4** — bind_host alignment, validator
   de-duplication, dev-mode ergonomics. Bundle.
8. **qj5.13.5** — wrong-prefix structural-guard test (≈10 lines).
9. **qj5.16.13.5** — "Use in allowlist" UX gating.
10. **P3 tail** — qj5.13.2/.3/.9, qj5.15.3, qj5.16.13.4, qj5.16.15.

## 6. Critical-path observations from the run

The audit surfaced four classes of finding worth carrying forward
into Saturn's longer-term posture:

1. **The "single TOFU per service-name" axiom.** §14.4.1 + qj5.16.13
   shipped this. Every Saturn deployment now refuses silent rebind
   to a higher-priority new node_id without admin attestation. This
   is the structural answer to "anyone on the LAN can claim to be
   Saturn." Worth marketing.

2. **TLS authenticates the chosen endpoint, not the choice of
   endpoint** (§14.3). Closing F-7 (TLS) without F-8 (mDNS identity)
   would have left a gap that a determined LAN attacker could ride.
   The audit's framing here protected against a bad ship decision.

3. **SSR pre-fill defeats bearer-fetch-override** (qj5.13.7
   regression). When server-side renders user-specific data and the
   page route loses its auth gate, the AJAX bearer flow is
   structurally bypassed. Hardener restored auth on the route; the
   pattern remains a footgun for any future SSR work.

4. **Aggregate-now / HIGH-if-extended** (§9 framing for usage table).
   Today's privacy disclosure is bounded because the schema only
   holds aggregate counts. If a future telemetry change adds
   per-model or per-conversation fields, the existing
   `?user_id=<ip>` bypass would promote from MEDIUM to HIGH. Note
   the hedge so future implementers don't rebuild on top of it.

## 7. Commits referenced

Audit-side: `4200c1b`, `4506373`, `a3fb68a`, `20a7da5`, `7ae4d07`,
`a8b02c2`, `c87ec3d`, `5e65912`, `20fe48a`, `75dd610`, `38962eb`,
`8f35d3a`, `db74a14`, `375c616`.

Implementer-side (vetted during run): `8b1e54d`, `26d20e1`, `150468c`,
`70f7beb`, `b38b4af`, `3a27eeb`, `c9347a0`, `ebe57f8`, `3de812c`,
`437ee7b`.

## 8. How to use this file

- **Re-entering the audit trail:** §1 → §2 give the section/bead
  shape; §3 is the bead truth-table.
- **Picking next work:** §5 lists the open queue in priority order
  with pre-spec section pointers.
- **Justifying a structural decision against an audit finding:** §6
  has the four cross-cutting framings; the matching SECURITY_AUDIT
  section has the full reasoning.
- **Tracing a finding's lifecycle:** F-thread → audit § → bead → fix
  commit. Every closed finding has all four breadcrumbs.

---

*End of run summary. SECURITY_AUDIT.md is the developer-shaped
reference; PRE_SPECS_B3.md is the implementer-shaped pre-spec set;
docs/admin/configure.md (writer) is the admin-shaped runbook. This
file is the index that ties them together.*
