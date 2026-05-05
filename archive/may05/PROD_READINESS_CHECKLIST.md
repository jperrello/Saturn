# PROD_READINESS_CHECKLIST.md

Branch: `autonomous/promo-push` → `main`. Tip: `c53760c`. Forked from MAY04 tip `50750fe` (33 commits).

Operator checklist before merging. Sourced from `RUN_NOTES_MAY{04,05}.md`, `FINAL_VERDICT.md`, `LANDING_DEMO.md`, `DISCOVERY_AUDIT.md`, `PARITY_REVIEW_MAY05.md`, `FAILOVER_SECURITY.md`, `SECURITY_AUDIT.md`. Items are listed in **must-do → nice-to-have** order. Each row cites the source so you can drill in.

---

## 0. Merge blockers (do not merge until cleared)

**Live-state check** (verified 2026-05-05 against `bd list --status open --json`): **no open MERGE BLOCKERS from this run.** All five P1/in-progress items previously listed here have shipped + closed:

| Bead | What | Closing commit |
|---|---|---|
| Saturn-xqw | `api_base` TXT trust — SSRF / route hijack | `127f708` |
| Saturn-93w | TOFU pin-race | `5930a72` |
| Saturn-zd6 | `_failover_state` unbounded sticky-map DoS | `8c91f1f` |
| Saturn-68j | `_failover_state` residual DoS gap | `7222aba` |
| Saturn-3d9 | cbt.5.1.ui Web-UI consumer of new `/api/discover` shape | `b6b184f` (bundled) |
| Saturn-9ha | cbt.2.d-D mid-stream edit-save drift | `dcf235b` |

**Re-verify before declaring merge-ready** — run `bd list --status open --json` and confirm the run-scoped P1 set (security-labelled or `cbt.*` parented) is empty. Surviving open P2/P3 from this run are tracked under §7 follow-ups; surviving P2 from prior runs (Saturn-o4r split-brain, qj5.16.13.5 allowlist UX, qj5.14.2 bind_host validator, qj5.16.12 TLS auto-cert) are intentional deferrals, not blockers — confirm with athena before merge if any have escalated.

Run epics that close on child-bead closure (`Saturn-cbt`, `Saturn-cbt.2`) and unrelated open epics (`Saturn-gww*`, `Saturn-fw6`) are out of scope for this merge. **Saturn is still a LAN-trust system** — `api_base` validation + TOFU pre-seed close the active spoofing vectors, but the design intent assumes the LAN itself is trusted; do not expose admin endpoints to untrusted networks regardless of bd state.

---

## 1. Environment variables (set before first boot)

| Var | Required? | Default | Notes |
|---|---|---|---|
| `SATURN_ADMIN_PASSWORD` | **YES** for any admin endpoint | unset → 401 | qj5.16.2 admin bearer wrapper. Bombadil harness currently lacks this — Saturn-3bq filed. |
| `SATURN_RUNNER_TOKEN` | **YES** for `/v1/*` | unset → 401 fail-closed | `saturn/runner.py:453-469`. Constant-time HMAC compare. **Token-distribution** is the open design question — currently shared-cluster (see SECURITY_AUDIT addendum §2). For demo/closed-LAN: one shared token. For production: open epic before going public. |
| `SATURN_RATE_RPM` | optional | 30 | `saturn/web.py:228`. Per-IP RPM cap on chat endpoints. Note: `/api/discover` is **not** rate-limited today (P2 fold-in to cbt.5.1; see FAILOVER_SECURITY phase-4 §C). |
| `SATURN_PREFER_V6` | optional | `0` | cbt.7.prefer. When set, `connect_address(service)` prefers AAAA over A; v6→v4 fallback on connect timeout. Leave unset on v4-only LAN. |
| `SATURN_ADVERTISE_ALL` | optional (planned) | `1` | cbt.6 / Saturn-oqh — currently always-on; flag is for opt-out. |
| `SATURN_TXT_CEILING` | optional | `1200` | cbt.8 / Saturn-oqh — bytes; raise only on jumbo-frame networks. Lowering risks `TxtTooLarge` at register. |
| OpenRouter / upstream API keys | depends on backend | unset | Per `runner.config.upstream.api_key_env`. Set in the runner's environment, not in TXT. |

Saturn-oqh tracks centralising the new `SATURN_ADVERTISE_ALL` / `SATURN_PREFER_V6` / `SATURN_TXT_CEILING` knobs into the same `CONFIG_FIELDS` schema as the MAY04 admin config.

---

## 2. Allowlist + trust-anchor setup

| # | Item | Notes |
|---|---|---|
| 2.1 | `~/.saturn/known_nodes.json` permissions: `0600`. Verify with `ls -l`. The save path enforces this (`saturn/mdns/known_nodes.py:55`) but a pre-existing file from earlier installs may be `0644`. | DISCOVERY_AUDIT §c |
| 2.2 | If you have an existing peer roster, **pre-populate `known_nodes.json`** with operator-asserted `name → node_id` pins **before** opening the LAN. This is the only mitigation for Saturn-93w that lands without code change. | FAILOVER_SECURITY §A |
| 2.3 | Sibling `~/.saturn/known_nodes.json.lock` file is created automatically on first mutator (cbt.3.c, `fcntl.flock`). Confirm the directory is writable by the Saturn user. | RUN_NOTES_MAY05 §B.1 |
| 2.4 | `~/.saturn/allowlist.json` (planned, Saturn-93w mitigation): not yet shipped. Until it is, **do not run on a LAN with untrusted peers**. | FAILOVER_SECURITY §A |

---

## 3. Log expectations (what should appear / what should not)

**On boot**, you should see:
- `Registered <name> on _saturn._tcp.local. at port <p> with priority <pri>` — `saturn/discovery.py:535`.
- One line per routable-address advertise (cbt.6.userspace).
- AAAA advertise lines if dual-stack (cbt.7.advertise).
- `mtrunc=1` warning iff the TXT was pruned (cbt.8.integrate). Investigate config if unexpected.

**On peer churn**:
- `Removed Saturn service: <name>` on goodbye / TTL expiry / sweep_stale.
- INFO-level pin record on first PIN_CONFIRMATIONS-confirmed TOFU.
- WARN on rebind rejection (a different `node_id` for an already-pinned name) — investigate immediately.

**Never expected** (treat as incident):
- `TxtTooLarge` at register without an explainable config-bloat cause — points at upstream that's bloated `models` / `capabilities` / `features` lists.
- Repeated rebind-rejected for the same name — possible Saturn-93w spoofing attempt.
- `_failover_state` size growth that doesn't track legit conversation count — possible Saturn-zd6 exploitation (or legit traffic; correlate with per-IP RPM).

---

## 4. Smoke tests (run before declaring green)

Run from repo root with the Saturn venv active.

```bash
# 4.1 Unit / integration suite
pytest saturn/tests/ -x --tb=short
# Expected: all green at land per RUN_NOTES_MAY05 §Test counts.

# 4.2 Failover acceptance (real subprocess peers; takes ~60s)
pytest saturn/tests/test_failover_cbt4.py -v
# Expected: 4/4 — covers active-5xx switch <2s, 2x-fail health gate, sticky, per-model affinity, routing.events receipt.

# 4.3 mDNS edge cases
pytest saturn/tests/test_isolation_cbt5.py saturn/tests/test_routable_addrs_cbt6.py \
       saturn/tests/test_dual_stack_cbt7.py saturn/tests/test_txt_validate_cbt8.py -v

# 4.4 Discovery hardening
pytest saturn/tests/test_discovery_settle_cbt3a.py \
       saturn/tests/test_discovery_max_age_cbt3d.py \
       saturn/tests/test_known_nodes_cross_proc_cbt3c.py \
       saturn/tests/test_userspace_parallel_resolve_cbt3b.py -v

# 4.5 Web-UI / Bombadil — REQUIRES SATURN_ADMIN_PASSWORD set (Saturn-3bq)
SATURN_ADMIN_PASSWORD=test-admin tests/bombadil/run.sh
# Expected: cbt.2.{a.ui, b}, cbt.bny green; LANDING_DEMO §8 captures regenerated.

# 4.6 Manual discovery probe on the deploy network
python3 -c "from saturn.discovery import discover; print(discover(timeout=8.0))"
# Expected: list with the peers you expect, no surprise entries.

# 4.7 AP-isolation probe (run on a deliberately AP-isolated network if possible)
python3 -c "from saturn.mdns.isolation import probe; print(probe(timeout=4.0))"
# Expected on healthy LAN: self_seen=True, suspected_ap_isolation=False.
# Expected on eduroam/guest: self_seen depends; suspected_ap_isolation=True.
```

---

## 5. Deploy gotchas

| # | Gotcha | Source |
|---|---|---|
| 5.1 | **`psutil>=5.9.0` is now required** for cbt.6 multi-NIC support. Already pinned in `pyproject` (`f99354d`); confirm pip resolved it. | RUN_NOTES_MAY05 §B.3 |
| 5.2 | **macOS Bonjour SPS freezes TXT during sleep.** If a peer goes to sleep and back, expect a brief window where its TXT reports stale data. cbt §16.4.2 unregisters rather than relying on TTL. | qj5.16/§16, RUN_NOTES_MAY04 |
| 5.3 | **`/api/discover` is unauthenticated and runs `~9s of work per request`** (5s discover + 4s isolation probe). Do not expose to the public internet under any circumstance. Bind `127.0.0.1` for the admin port (qj5.16.1 default). | FAILOVER_SECURITY phase-4 §C |
| 5.4 | **`SATURN_PREFER_V6`** changes connection ordering. Verify upstream services actually accept v6 before flipping; some Ollama builds bind v4 only. | RUN_NOTES_MAY05 §B.3 |
| 5.5 | **`mtrunc=1`** propagates downstream — clients that read TXT `models` see a truncated list. UI should reflect this (e.g., "model list partial — see /v1/models for full"). | cbt.8.integrate |
| 5.6 | **Cross-process `known_nodes` lock** uses sibling `.lock` file. NFS / tmpfs filesystems may have flock semantics quirks; use ext4/APFS. | cbt.3.c |
| 5.7 | **Receipt envelope `saturn_meta` ships in every chat surface** (cbt.1). Old clients that don't strip unknown keys may fail; confirm client tolerance before rollout. | RUN_NOTES_MAY05 §A |
| 5.8 | **AP-isolated networks (eduroam, UCSC-Guest, most hotel Wi-Fi) break mDNS.** The probe will report `suspected_ap_isolation=True`; users must use manual config. Document in user-facing rollout notes. | RUN_BRIEF_MAY03 §6.1.2; cbt.5.1 |
| 5.9 | **Two Saturn instances on one host is supported** but only since cbt.3.c. Earlier branches will lose pins. Do not roll back below `8d2bbfd` if you started using two-instance-per-host. | cbt.3.c |
| 5.10 | **`/v1/*` shared-token assumption** — every peer accepts the same `SATURN_RUNNER_TOKEN`. Compromise of one peer = compromise of all. Acceptable for closed-LAN demo; needs per-peer flow before public-LAN. | SECURITY_AUDIT phase-4 §2 |

---

## 6. Rollback procedure

If a regression appears post-merge:

```bash
# 6.1 Identify the offending commit range
git log --oneline 50750fe..main

# 6.2 If the issue is contained to one bucket, revert that bucket's commits
# Bucket A (polish):    347bdc9, 5ac0a28, 83633d3, 4961da8, 417ba93, plus cbt.2.a/b commits
# Bucket B.1 (discovery): 75c58f9, 2c9ef90, 8d2bbfd, fa57189, c53760c
# Bucket B.2 (failover):  4f05fdb
# Bucket B.3 (mDNS edges): 5c7410c, b6b184f, f99354d, 78b0a64, d30e014, e7b6adf, 0ccab52, 3a2cc30, 189a86d, 173ad9e, 6df7367

# 6.3 Full rollback to MAY04 tip
git revert --no-commit 50750fe..main
git commit -m "Revert promo-push MAY05 run"
git push origin main

# 6.4 known_nodes.json compatibility
# Schema is back-compat; rollback does not require deleting the file.
# But the cross-process .lock sibling will be ignored by pre-cbt.3.c code — safe.

# 6.5 Receipt envelope (saturn_meta) consumers
# The new fields land additively; rolling back to MAY04 keeps the on-/api/chat
# envelope but loses /api/proxy/chat and runner /v1/chat/completions emission.
# Clients that came to depend on the lifted surface will see absent saturn_meta —
# update their code OR keep /api/chat as their source of truth.

# 6.6 Branch hygiene
# Do NOT delete autonomous/promo-push after merge — keep for at least 2 weeks
# in case a partial rollback is needed.
```

If only the security P1s (Saturn-{zd6,xqw,93w}) are the concern: **do not roll back the whole run** — apply targeted patches per their bead descriptions. The rest of the run (polish + discovery hardening + mDNS edges) is independently valuable.

---

## 7. Post-merge follow-ups (non-blocking but tracked)

These are open beads that should land in a near-term follow-up wave but do not block the merge itself:

| Bead | What | Severity |
|---|---|---|
| Saturn-oqh | Centralise `SATURN_ADVERTISE_ALL` / `SATURN_PREFER_V6` / `SATURN_TXT_CEILING` into `CONFIG_FIELDS` | P2 |
| Saturn-b3o | `/api/system/chat` rate-limit (separate from per-IP RPM) | P2 |
| Saturn-zor | `/api/system/chat` token validation | P2 |
| Saturn-b5a | cbt.5 Web-UI integration of `/api/discover` `isolation` key | P2 |
| Saturn-5ir | cbt.5 adversarial real-network AP-isolation cases | P3 |
| Saturn-3bq | `tests/bombadil/run.sh` missing `SATURN_ADMIN_PASSWORD` env | P3 |
| Saturn-v60 | `demo/_capture_cbt_4.py` vs test-fixture single-source-of-truth | P3 |
| Saturn-b46 | Populate mDNS TXT records with models for custom module servers | P3 |
| MAY04 carry-overs | `qj5.13.{1,2,3,5,8,9,10}`, `qj5.14.{2,3,4}`, `qj5.15.{1,3}`, `qj5.16.{12,13.4,13.5,15}` | mixed P2/P3 |

---

## 8. Sign-off

Before merging, paste a sign-off block in the PR:

```
[ ] §0 merge blockers re-verified empty via `bd list --status open --json` (Saturn-{xqw,93w,zd6,68j,3d9,9ha} closed at land; confirm no new run-scoped P1 has appeared since)
[ ] §1 env vars set on the deploy host
[ ] §2 known_nodes.json + allowlist hygiene verified
[ ] §4 smoke tests green (paste test counts)
[ ] §5 gotchas reviewed against deploy network (multi-NIC? IPv6? AP isolation? two-host?)
[ ] §6 rollback procedure reviewed; branch retained
[ ] §7 follow-ups filed and assigned
```
