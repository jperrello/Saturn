# Run Brief — 2026-05-05 (autonomous, 8-hour cap)

Branch: `autonomous/promo-push` (continue, push as you go).
Overseer: parent orchestrator. **User is out of the loop.** No escalation.
Router: **athena**.
Hard stop: **8 hours from kickoff** — overseer auto-lands at the cap.

## Continuity

This run continues directly from the MAY04 run. Read first:
- `RUN_BRIEF_MAY04.md` — prior brief
- `RUN_NOTES_MAY04.md` — handover doc
- `FINAL_VERDICT.md` — test counts
- `FINAL_AUDIT_SUMMARY.md` — security audit index
- `LANDING_DEMO.md` — demo capture index
- `PRE_SPECS_B3.md` §17.A–F — Bucket-3 implementer pre-specs

**All workers must clear-and-talk between context switches** — last run's per-worker context bloat must not bleed into this run. Athena: enforce via `crew.sh clear-and-talk` whenever a worker pivots between buckets or finishes a major bead.

## Two buckets

### Bucket A — promo-push polish (finish what's tracked-deferred)

**A.1 — Saturn-qj5.15.2** (already filed P2)
Lift the `saturn_meta` receipt envelope from `/api/chat` to the other 3 chat surfaces per PRE_SPECS_B3.md §17.F. Four surfaces inventoried with file:line cites:
1. `/api/proxy/chat` (saturn/web.py:848-885) — direct lift
2. `/v1/chat/completions` on the runner (saturn/runner.py)
3. The non-streaming `/api/chat` parity path (already done — verify)
4. Brutus Discord bridge if it surfaces resolved config (check brutus/bot.py)

Acceptance: every chat surface returns `saturn_meta` with `schema_version=1`, `applied.{max_tokens,temperature,model,system_prompt_sha256}`, `verifiability.{token_cap_observed,model_observed,...}`. No mocks; tested against real Ollama + at least one OpenRouter sub-key.

**A.2 — Bucket-1 chat UX hardening**
Bombadil + playwright extended coverage of chat UX edge cases:
- Long messages (>4k tokens, >32k tokens) — UI doesn't freeze; receipt still arrives
- Attachments via the new `+` menu — file types, size limits, error states
- MCP edge cases — MCP server unreachable, tool call timeout, oversized tool result
- Edit-and-regenerate flake — rapid-fire edits, edits during streaming, edits with attachments

Brutus authors per-edge-case contracts; hardener implements; demo captures.

### Bucket B — new feature work (the centerpiece of this run)

**B.1 — Saturn discovery improvements**
Tune `saturn/discovery.py` + `saturn/mdns/`:
- Settle detection — review against §16.6 + RUN_BRIEF_MAY03 patterns; tune for stability
- Parallel resolves — currently serial in `discover()`; profile + parallelize where safe
- Identity collision handling — TOFU + allowlist exists (qj5.16.13); verify under churn (rapid add/remove of same node_id)
- Cache strategy — what does the discovery cache TTL actually look like? Document + test

Geoff produces DISCOVERY_AUDIT.md before brutus contracts; oracle clarifies thesis intent for any ambiguous behavior.

**B.2 — Client-side failover (FULL spec)**
Falsifiable success criterion (locked by user):
- **Timeout-driven switch:** when current service `/v1/health` fails 2x consecutively (or active request returns 5xx), client transparently switches to next-priority service. **Measured: <2s switch latency** end-to-end.
- **Sticky session:** after switch, stay sticky to the new service. Do NOT oscillate back when the original recovers. Stickiness lasts until the new service ALSO fails (then go to next-priority).
- **Per-model affinity:** only switch to a service that advertises the requested model. If no peer service has the model, fail with a clear, helpful error (NOT a silent retry on a wrong model).
- **Receipt integration:** `saturn_meta` receipt (qj5.15) must show which service handled this turn AND any failover events that occurred during the turn (e.g., `saturn_meta.routing.events: [{from: <id>, to: <id>, reason: "health_timeout", at: <ts>}]`).

**No mocks.** Test by spinning a second Saturn server on a different port via the harness (qj5.7), making one fail (kill it / block its port), and verifying the client-side switch lands within 2s. Brutus owns the contract; hardener implements.

**B.3 — mDNS edge cases (all four)**

- **AP isolation detection + workaround.** Detect "I can advertise but no peers see me" / "I can browse but find nothing despite known peers existing" — surface a clear UI error in the Web-UI Network Scan tab with a "switch to manual config" link. Reference RUN_BRIEF_MAY03 §6.1.2 (eduroam/UCSC-Guest blocks Saturn).
- **Multi-interface (Wi-Fi + Ethernet).** Server with multiple NICs currently advertises one address only; clients on the other interface don't see it. Fix: bind to all interfaces, advertise A records for each routable address. Test with a real multi-NIC machine via harness.
- **IPv6 / dual-stack.** Add AAAA records to advertisements. Prefer IPv6 when both available. Handle dual-stack gracefully (don't double-up the same service).
- **Large TXT records / fragmentation.** TXT >1500 bytes risks fragmentation or drop. Add advertise-time validation that hard-fails if TXT exceeds safe size. Document the safe ceiling.

Geoff pre-specs each edge case (one per §17.G subsection) before brutus contracts.

## Hard rules (carry over from MAY04)

- Push to `autonomous/promo-push` only. **Never main.**
- **No mocks** in tests. Real backends, real LLMs, real Saturn services, real network.
- Code style: python3, no docstrings, single-word names, early returns no else.
- After any change to `saturn/web.py` or Web-UI: run `tests/bombadil/run.sh`.
- UI claims must be verified in a browser via playwright/rodney. Type-checks ≠ works.
- bd workflow: mark in_progress before coding; close on commit.
- **No escalation to user.** Overseer decides.
- **clear-and-talk between context switches.** Athena enforces.

## Coordination

- This file (`RUN_BRIEF_MAY05.md`) is the canonical context. All crew read it first.
- bd is the work ledger. Sub-beads under epic `Saturn-MAY05` (TBD ID after creation).
- Athena owns the dependency graph; ticks every 15 min.
- Tmux scrollback is ephemeral.

## Done = shipped

- Branch pushed; epic Saturn-MAY05 closed.
- A.1 + A.2 green.
- B.1 + B.2 + B.3 each have at least one demoable artifact (showboat capture or LANDING_DEMO entry) + green tests.
- New `RUN_NOTES_MAY05.md` handover doc shipped.
- 8h cap respected — unfinished work files as deferred follow-up beads, not partial commits.
