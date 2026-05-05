# RUN MAY05 — Web UI + Docs overhaul (autonomous/promo-push)

User out-of-loop. Overseer = parent claude. Router = athena. All work commits to `autonomous/promo-push`.

## Locked decisions (do not relitigate)

### Web UI
- **Whole UI is gated** behind admin password. Default = `Saturn`.
- **Auth model:** server-verified session cookie. Password hash stored server-side. First-run + change-password flow. Most secure of the options on the table.
- **Pages, in order:** Network Scan → System → Chat. **Remove** the standalone Admin Configure page; remove the admin-password field from Network Scan (now redundant — whole site already gated).
- **Field validation:** admin-config form and new-service form must *test* fields server-side (live health check / cred verification) before save. No silent saves.
- **Number inputs → text inputs.** No spinner arrows anywhere. Complex fields (e.g. public_routes) get an `(i)` info bubble that shows a short description on click.
- **max_budget unit toggle:** USD ↔ tokens. Persist unit alongside value.
- **Chat input bar:**
  - `+` (add) menu lives **inside** the message bar, mirroring the send button.
  - Plus icon must be **white on transparent** (currently invisible on white bg).
  - MCP moves into the `+` menu. Remove the top-right MCP button next to settings.
  - MCP popup gets an explicit `X` close button.
- **Settings panel:** drop response-style / model-override / saturn-service. Replace with OWUI-style model params: temperature, top_p, top_k, max_tokens, system prompt + any additional params gullivan finds worth exposing. **Each param must be verified to actually affect Saturn responses** (live diff test) before shipping.

### Docs
- **Tabs (final):** Home / Tutorial / Integrations / Spec. (4 total.)
  - **Home** absorbs current Quick Start + Tutorial landing + "Saturn on the wire" content.
  - **Tutorial** absorbs current How-To Guides.
  - **Integrations** absorbs Implementations (or Implementations is removed if redundant).
  - **Spec** = renamed Reference. mDNS-at-OS-level content lives here.
  - **Concepts tab is removed entirely.**
- **Thesis link:** https://escholarship.org/uc/item/74r4d4c5#main — propagate across README, docs Home, citations.
- **Repo root cleanup:** drop stray `.md` artifacts from prior autonomous runs (run-notes, FAILOVER_DEMO.md, PRE_SPECS_*.md, etc). Keep canonical only.
- **README codeblocks:** several fences are broken/unterminated — fix.

## Beads (filed)
- Web UI: Saturn-k28, 2wc, c7z, 7rr, f3o, zc7, 8ve (+ the gate bead, see `bd list -l webui`)
- Docs: Saturn-jn0, zz5, 5xd, uqk

## Lane assignments
- **hardener** — web UI code changes (auth gate, page collapse, input refactor, chat bar, MCP, settings rewrite). All Saturn-k28/2wc/c7z/7rr/f3o/zc7/8ve and the auth gate bead.
- **bombadil** — Playwright contracts + verification for every web UI change. Especially: test that field-validation actually rejects bad input; that settings params actually change model output (diff-based attestation).
- **gullivan** — research: which OWUI / OpenAI-compatible params are worth exposing in settings beyond temp/top_p/top_k/max_tokens/system_prompt. Two-pass: rough list fast, full ranked list after.
- **writer** — docs IA collapse, README codeblock fixes, thesis link propagation. Saturn-jn0, zz5, uqk.
- **oracle** — read-only ground truth on thesis claims / "Saturn on the wire" content that needs to move to Home.
- **demo** — repo root cleanup (Saturn-5xd) — owns autonomous-run artifacts already.

## Rules
- python3, no docstrings, single-word names, early returns, no mocks in tests.
- Commits only to `autonomous/promo-push`.
- Workers report back to **athena**, not directly to overseer.
- Watchdogs already running (pid 723 unblocker, 727 ghostty-yes).
