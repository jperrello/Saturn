# Run Brief — 2026-05-04 (autonomous, open-ended)

Branch: `autonomous/promo-push` (push as you go).
Overseer: parent orchestrator. **User is out of the loop.** No escalation.
Router: **athena**.

## Three buckets (parallel, fluid crew assignment)

Crew is NOT locked to one bucket. Brutus, Gullivan, Athena, Geoff range across all three. Forge spawns new lanes if a recurring gap appears. Locals (oracle, hardener, writer, demo) anchor the Saturn-specific work.

---

### Bucket 1 — Chat UX overhaul (gates: real Saturn server, real LLM tokens)

Target screen: web-ui Chat tab (see image #1 in conversation; describe in CONTEXT for crew).

Required changes:

1. **Remove top-right "Default / Detailed / Concise / Code" response-style pill.** Relocate to the per-chat popup (see #3).
2. **Replace the Saturn SVG (top-left) with a Settings button.** Discoverability — users must understand what that control opens (Nielsen H4 consistency, H6 recognition not recall). Clicking opens a per-chat **popup menu** (same pattern as the current settings page) containing:
   - Response style (Default/Detailed/Concise/Code)
   - Model override for this chat
   - Current Saturn service
3. **MCP TOOLS list → popup menu.** Same pattern as settings popup. Add an intuitive "Add MCP server" flow inside the popup (the current `SERVERS` button is non-obvious).
4. **Replace the 5 unlabeled icons above the chat bar with an Image #2-style `+` menu.** Items in the menu (FINAL list — do not add others):
   - Attach file/photo
   - MCP tools / Connectors
   That is it. The relocated response-style lives in the Settings popup (#2), not here.
5. **Fix Send button vertical alignment with the chat input.** Currently misaligned.
6. **Edit-sent-message — Claude/ChatGPT-style.** After a user sends a message, they can edit it; editing truncates the conversation at that turn and regenerates from the edit.

**Testing requirement (HARD):** every change verified against a *real running Saturn server*. The crew must, as part of the test loop:
- Add new Saturn services from scratch (do NOT only edit pre-existing config files).
- Discover them via the web UI.
- Edit their config and verify the edit propagates end-to-end.
- Delete them and verify removal.
- Send real chat traffic that hits a real LLM (Ollama for free turns, one keyed Saturn server for end-to-end).

Brutus may use playwright + rodney to enumerate features, then write tests against them. If we have other observability that would aid him better, he should propose it; otherwise that is the path.

---

### Bucket 2 — Docs / README (writer + gullivan + oracle)

1. **Oracle:** equip with the RLM skill (`/chomp` infra) so it reads .md files efficiently.
2. **Gullivan (research librarian):**
   - Read documentation sites for mDNS protocols, Python packages, Go projects, etc. Goal: internalize what *good* doc sites look like.
   - Read READMEs in mDNS-adjacent and similar GitHub projects. Goal: internalize the 5-second-decision README bar.
   - **Gullivan may spawn new crew** via forge if he finds GitHub projects / agent-authoring techniques that produce better READMEs/docs than current crew. If new crew underperforms, tune; if it succeeds, keep using.
3. **Writer:** rewrite README and docs/ with the inputs above:
   - More codeblocks.
   - Less repetition.
   - README and docs serve different audiences — README is the 5-second-decision artifact; docs hold the depth.
   - Saturn = a protocol, not a Python package. Curl/Go examples lead; Python is one implementation.

---

### Bucket 3 — Configuration page + LLM-config proof + Security (the real concern)

The user is the publisher of Saturn and is *not convinced* the config we expose (Web-UI Configure page, Python config, Go/Lua config, TXT records) actually applies to the LLM. Example: if a user sets `max_tokens=50`, does the LLM truly stop at 50 tokens? **There is currently no test that proves this end-to-end.** Build it.

#### 3a. Settings split

- **Server-wide → admin Configure page** (Network Scan tab → Configure):
  - max_tokens, temperature, model defaults, API keys, MCP servers, etc.
- **Per-chat → Settings popup** (in chat tab, behind the new Settings button):
  - Response style, model override, current Saturn service.

#### 3b. Configuration **proof tests** (full bar — tests + receipt + security)

For every config field exposed via TXT records and/or the Configure page, write an automated assertion test:

- `max_tokens=50` → response token count ≤ 50.
- `temperature=0` with same prompt → deterministic output across N calls.
- `model=<X>` → response actually came from model X (verify via response metadata or output fingerprint).
- `system_prompt=<S>` → S provably influenced output.
- Repeat for every field. **No mocks.** Hit a real LLM. Use Ollama for the bulk of churn-tests (free), with one keyed OpenRouter or DeepInfra Saturn service for the end-to-end real-upstream pass.
- **Cover both paths:** (a) editing existing Saturn configs and verifying edits take effect, (b) creating brand-new Saturn services from scratch and verifying their config takes effect.

#### 3c. Live UI receipt

In the chat UI, display the **resolved config used for each assistant turn** (token cap hit, temp, model, system prompt). The user must visibly see what the server actually applied.

#### 3d. Security audit

- Are TXT records visible to anyone on the LAN? Document the exposure surface.
- Are any API keys ever exposed in TXT records, web responses, or local files readable by other users?
- Threat model: who can do what to a Saturn service on a multi-tenant network?
- Fixes for any vulnerabilities found.
- **Verify llama endpoints actually work** — the user is unsure.
- Expand the config field set if the audit reveals security-relevant fields the user should be able to set.

This bucket gates the user's willingness to promote Saturn to administrators. Treat it as production work.

---

## Environment

- `.env` at Saturn root — already populated with `OPENROUTER_API_KEY`, `OPENROUTER_PROVISIONING_KEY` (mgmt key), `DEEPINFRA_API_KEY`. **Never commit.** `.gitignore` covers `*.env`.
- OpenRouter management API: `Authorization: Bearer <PROVISIONING_KEY>` to `https://openrouter.ai/api/v1/keys` — POST creates runtime sub-keys (body: `{"name": "...", "limit": <usd>}`), GET lists, PATCH updates (`disabled`, `limit_reset`), DELETE revokes. Use this for per-test sub-keys so we don't burn the parent.
- Ollama runs locally; assume the small models it pulls by default are fine.

## Hard rules

- Push to `autonomous/promo-push` only. **Never main.**
- **No mocks** in tests. Real backends, real LLMs, real Saturn services.
- Code style: python3, no docstrings, single-word names, early returns no else.
- After any change to `saturn/web.py` or Web-UI: run `tests/bombadil/run.sh`.
- UI claims must be verified in a browser via playwright/rodney. Type-checks ≠ works.
- bd workflow: mark in_progress before coding; close on commit.
- **No escalation to user.** Overseer decides.

## Coordination

- **This file** is the canonical context. All crew read it first.
- **bd** is the work ledger. Sub-beads under epic `Saturn-MAY04`.
- **Athena** owns the dependency graph and ticks every 15 min.
- Tmux scrollback is ephemeral — never load-bearing.

## Done = shipped

- Branch pushed.
- All Bucket-1 UX changes verified live in browser against a real Saturn server.
- Bucket-2 README + docs reframed; new crew (if any) documented.
- Bucket-3 proof test suite green; UI receipt visible; security findings filed (and fixed where critical).
- bd Saturn-MAY04 children all closed or follow-ups filed.
