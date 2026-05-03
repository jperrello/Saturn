# Web-UI Feature Inventory — Saturn-gww.4

Generated 2026-05-03 via Playwright MCP click-test of every visible control in
the Web UI (http://localhost:3000/, served by `python3 -m saturn web`).

Legend: **OK** = works as expected. **BROKEN** = action fails or wrong outcome.
**UNCLEAR** = label/affordance ambiguous, control may work but is hard to find
or interpret.

---

## Top-level tabs

| Control | Status | Notes |
|---|---|---|
| `NETWORK SCAN` tab | OK | switches to discover view |
| `SYSTEM` tab | OK | switches to system view, lands on Integrate sub-tab |
| `CHAT` tab | OK | switches to chat view |

## NETWORK SCAN view

| Control | Status | Notes |
|---|---|---|
| `#discover-btn` ("NETWORK SCAN") | UNCLEAR | works, but label flips to "DISCOVER" after first click — same control, two names. Pick one (Saturn-gww.4a). |
| zero-result feedback | BROKEN | when scan finishes with 0 services, no status/empty-state appears. User can't tell if scan ran. (Saturn-gww.4b) |
| `#admin-pw-submit` ("UNLOCK") | BROKEN | empty-password submit silently no-ops. No error, no toast. (Saturn-gww.4c) |

## SYSTEM > INTEGRATE

| Control | Status | Notes |
|---|---|---|
| `#tab-integrate` | OK | active by default |
| connector cards × 9 (OpenCode, Codex, Continue, Aider, Cline, Cursor, Claude Code, OpenClaw, Generic) | OK | each opens an inline detail panel with endpoint + key + config snippet |
| `#connector-key-reveal` (SHOW/HIDE) | OK | toggles api-key reveal, updates label |
| `.connector-copy` (COPY × N) | OK (visual) | not destructively tested but standard clipboard behavior |
| `#connector-test-btn` (Test Connection) | BROKEN | hits a 404 endpoint and reports "Server returned 404". Client points at `/v1/health`-like path but server is not exposing it under `/api`. (Saturn-gww.4d) |
| `#connector-close` | OK | collapses detail panel |
| `Full Integrator Guide` link | UNCHECKED | not clicked (external) |

## SYSTEM > STATUS

| Control | Status | Notes |
|---|---|---|
| `#tab-status` | OK | shows Backend Health / Routing Activity / Usage Today sections with clear empty states |

## SYSTEM > REMOTE

| Control | Status | Notes |
|---|---|---|
| `#tab-remote` | OK | shows mode + tunnel button |
| `#proxy-tunnel-start` (Start Tunnel) | OK | starts cloudflare quick-tunnel, shows URL + "tunnel active" |
| stale tunnel URL fragment | BROKEN | tunnel URL is appended with `#brutus` (e.g. `https://…trycloudflare.com/#brutus`). Brutus tab was renamed to System; fragment must be `#system` or removed. (Saturn-gww.4e) |
| `#proxy-tunnel-stop` | OK | stops tunnel cleanly |
| `#system-accept` ("I Understand — Enable Remote Access") | NOT-SHOWN | gate did not appear in this session; may already have been dismissed. Verify gate persistence. (Saturn-gww.4f) |

## CHAT

| Control | Status | Notes |
|---|---|---|
| `#chat-accept` ("I Understand — Continue to Chat") | NOT-SHOWN | already accepted; same persistence note as system-accept |
| `#drawer-toggle` (history) | OK | opens left history drawer |
| `#drawer-close` | OK | |
| `#new-chat-btn` ("+ New") | OK (visual) | drawer-only |
| `#clear-chats-btn` ("Delete History") | OK (visual) | drawer-only, destructive — not invoked |
| `.chat-settings-btn` (Configuration) | UNCLEAR | only reachable from inside the drawer. Not discoverable from the main chat view. (Saturn-gww.4g) |
| `#tools-toggle` (MCP Tools) | OK | shows tools panel with empty-state copy "No tools — add an MCP server first" |
| `#tools-refresh`, `#tools-manage` (Servers) | OK (visual) | inside MCP panel |
| `#file-upload-btn`, `#thinking-toggle`, `#export-json`, `#export-md` | OK (visual) | fab buttons, all have `title=` tooltips. Worth aria-labels. (Saturn-gww.4h) |
| `#send-btn` | OK | correctly disabled when no model selected, `title="Select a valid model first"` |
| `#service-select`, `#model-select`, `#style-select` | OK (visual) | populated only after scan |
| starter prompts ("What is Saturn?" etc.) | OK (visual) | prefills chat input |
| `#summarize-btn`, `#summarize-dismiss` | UNREACHABLE | only appears once a long chat exists; not exercised |

## CONFIGURATION overlay (opened from drawer settings)

| Control | Status | Notes |
|---|---|---|
| `#scope-global` / `#scope-service` toggle | OK |
| `#ep-add` (Manual Endpoints / ADD) | OK (visual) | not invoked (would mutate config) |
| `#model-filter-save` (APPLY) | OK (visual) | |
| `#alias-add` (ADD alias) | OK (visual) | |
| `#preset-save`, `#preset-delete` | OK (visual) | delete is disabled until a preset exists |
| `#response-format-type` select | OK (visual) | |
| `#config-reset` (Reset All) | OK (visual) | not invoked (destructive) |
| `#config-overlay-close` | OK | |

## Console / network errors observed

These 4 endpoints 404 on every page load and are likely behind several
"silent failure" issues above:

- `GET /api/services` → 404
- `GET /api/rate-limit/status` → 404
- `GET /api/admin/config` → 404
- `GET /api/usage` → 404

Plus `app.js:935` logs `Failed to load services: SyntaxError: Unexpected token
'N', "Not found" is not valid JSON` — the client should not assume a 404 body
parses as JSON. (Saturn-gww.4i)

---

## Sub-beads filed

- Saturn-gww.4.1 — discover-btn label flips NETWORK SCAN→DISCOVER (UNCLEAR)
- Saturn-gww.4.2 — discover empty-state (BROKEN feedback)
- Saturn-gww.4.3 — admin UNLOCK silent no-op on empty pw (BROKEN feedback)
- Saturn-gww.4.4 — connector Test Connection 404 (BROKEN)
- Saturn-gww.4.5 — tunnel URL has stale `#brutus` fragment (BROKEN)
- Saturn-gww.4.6 — verify chat-accept / system-accept gate persistence
- Saturn-gww.4.7 — Configuration only reachable via history drawer (UNCLEAR)
- Saturn-gww.4.8 — fab buttons rely on `title=`; add aria-label (a11y)
- Saturn-gww.4.9 — JSON parse on 404 body; missing /api endpoints
