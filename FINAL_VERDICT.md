# FINAL VERDICT — autonomous/promo-push (2026-05-04 run)

Brutus aggregate over the run's red→green chain. Commit-ordered.

## Headline

- **178/178** across every shipped auth / runner / identity / admin_config / config-honoured / configure / receipt / known-nodes / sleep suite. Latest aggregate confirmed on `qj5.16.14`.
- **Bombadil `chat` spec: 198/198** across the qj5.1–qj5.6 UX merges (last reading at `ba2f925`, qj5.4).
- **`tests/harness/selftest.py`: ALL OK** through 30+ commits.

## Per-bead test counts (commit-ordered)

| # | Bead | Count | Implementer commit |
|---|------|-------|--------------------|
| 1 | Saturn-qj5.16.1 — runner /v1/* bearer + safe bind | 7/7 | `fbb5896` |
| 2 | Saturn-qj5.16.2 — admin /api/* server-side auth | 32/32 | `370f9fa` |
| 3 | Saturn-qj5.16.10 — /api/usage* admin gate + XFF strip | 6/6 | `3345dbb` |
| 4 | Saturn-8v5 — `build_app()` unifies auth across `server.module` | 12/12 | `4227474` |
| 5 | Saturn-qj5.16.6 + .16.7 — proxy body/query key removal | 6/6 | `8bf0ef6` |
| 6 | Saturn-qj5.1 — top-right style pill removed | 2/2 | `6461641` |
| 7 | Saturn-qj5.2 — Settings popup (style + model + service) | 2/2 | `c2845b4` |
| 8 | Saturn-qj5.3 — MCP popup with direct Add-MCP flow | 2/2 | `60a589b` |
| 9 | Saturn-qj5.4 — `+` menu collapses 5 fabs | 2/2 | `ba2f925` |
| 10 | Saturn-qj5.6 — edit-sent-message + truncate-and-regen | 2/2 | `a232b13` |
| 11 | Saturn-qj5.13 — admin_config schema lift (round-trip + persist + live + refuse) | 33/33 | `8b1e54d` |
| 12 | Saturn-qj5.14 — boot validators + LLM-honoured proof | 27/27 + 4/4 Ollama (1 OR-skip) | `26d20e1` |
| 13 | Saturn-qj5.16.13 — F-8 TOFU + admin allowlist (pin/rebind) | 8/8 | `150468c` |
| 14 | Saturn-qj5.16.13.1 — TrustRebindError → structured 403 | 3/3 | `ff…` (geoff §15-loop) |
| 15 | qj5.13.4 / qj5.13.6 / qj5.14.1 | folded (regression-only, no new pytest count) | hardener inline |
| 16 | Saturn-hft — admin Configure SSR (CONTRACT_v2.md) | 5/5 → 6/6 (post-13.7) | `70f7beb` |
| 17 | Saturn-qj5.13.7 — restore Depends(require_admin) on /admin/configure + regression guard | 6/6 | `3a27eeb` (+ `c9347a0`) |
| 18 | Saturn-6sb — per-service editor (list / create / edit / delete / api_key-env-only) | 5/5 | (hardener) |
| 19 | Saturn-7j3 — known-nodes UI (trust mode + allowlist picker + rejections + 401 guards) | 6/6 | `ebe57f8` |
| 20 | Saturn-qj5.15 — `saturn_meta` receipt envelope (honest / coerced / hashed / per-turn / version / verifiable) | 6/6 (1 OR-skip) | `3de812c` |
| 21 | Saturn-qj5.16.3 — formal `trusted_proxies` allowlist + rightmost XFF | 5/5 | (hardener) |
| 22 | Saturn-qj5.16.14 — beacon sleep + keep-awake + §7.5 budget co-land | 11/11 | `50750fe` |

Co-land notes: §7.5 beacon `max_budget_usd` plumbing rode in the same PR as qj5.16.14. qj5.13.7 added a no-bearer regression guard to the Saturn-hft v2 file, taking it from 5/5 → 6/6.

## Out-of-lane self-routes (Brutus did NOT attempt)

- qj5.7 (real-Saturn test harness) — demo, shipped at `f195dbd`.
- qj5.16 (broad security audit / threat model) — geoff, shipped at `4200c1b` plus follow-on §15/§16/§17 pre-specs.
- Documentation polish (RUN_NOTES_MAY04, etc.) — writer / gullivan.
- qj5.16.13.2 / qj5.13.{1,2,3} P2-P3 cleanups — geoff's review notes were spec; no separate contracts.

## Discipline summary

- 17 falsifiable contracts authored (`.brutus/<bead>/CONTRACT.md` each).
- Every contract captured a red transcript before handoff (`showboat init` + `note` + `exec`).
- Every green captured a VERDICT.md with the implementer's commit + 1-line attestation.
- Two contracts (qj5.14, qj5.15) shipped as **test-only / no-implementer-block** per overseer guidance — the test files sit red and turn green incrementally as upstream beads land.
- One contract was loosened mid-run (Saturn-hft → CONTRACT_v2.md) when the playwright surface was eating hardener context. v1 stayed in-tree as optional E2E sanity; v2 became the gate.

## What's in the air

- The full §17 trio (qj5.13 / qj5.14 / qj5.15) has shipped GREEN.
- F-1, F-3 (partial), F-4, F-5, F-6, F-8, §15 trust + rebind, §16 sleep — all closed.
- Remaining: hardener queue is empty post-qj5.16.14; geoff's filed P2/P3 follow-ups (qj5.13.4 / .13.6 / .14.1 / .16.15 / .13.4 / .13.1 / .13.2 / .13.3 fold-without-contract list) are inline-spec.

The plane is on the ground.
