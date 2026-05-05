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
