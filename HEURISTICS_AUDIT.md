# Saturn Web-UI — Nielsen Heuristics Audit

**Bead:** Saturn-gww.2
**Branch:** `autonomous/promo-push`
**Auditor:** geoff (repo-analyst)
**Date:** 2026-05-03
**Scope:** `Web-UI/index.html`, `Web-UI/app.js`, `Web-UI/styles.css`, `Web-UI/server.ts`
**Method:** Static audit of the live tree. Browser walk-through was blocked — Chrome's playwright profile (`mcp-chrome-3df4b35`) was held by a parallel session for the duration of this pass. All citations are file:line; severities account for likely runtime impact based on event wiring + CSS rules. Hardener should re-verify in browser before code fixes.
**Owner of fixes:** hardener (Saturn-gww.3). This document is **audit-only**.

---

## Severity scale

- **HIGH** — blocks a primary task, causes data loss, or breaks an entire user mental model
- **MED** — slows or confuses users on a primary path; recoverable
- **LOW** — polish / consistency / minor friction

## ROUGH-PASS — Top 5 (start here, hardener)

| # | Heuristic | Severity | Where | One-liner fix |
|---|---|---|---|---|
| 1 | H9 Error recovery | HIGH | `app.js:1081` `cfg-test` button label *replaces itself* with the error code (`Error 404`) and disappears 2 s later — no advice, no recovery. | Render a persistent error region under the field with status code, a likely-cause hint, and a "Retry" button; do not overload button text. |
| 2 | H1 Visibility of status | HIGH | `Web-UI/index.html:110` `discover-btn` label is `Network Scan`; `app.js:872` flips it to `Scanning...` then back to `Discover` (`app.js:909`) — three different verbs for one control, and there is no progress / count-of-services-found feedback during the 3 s mDNS wait. | Keep the verb stable (`Scan`), show a progress affordance (spinner + live count from `/api/discover` partials), and surface "found N services" when done. |
| 3 | H5 Error prevention | HIGH | `app.js:1089` Save button posts immediately on click; the only validation is `if (!name \|\| !baseUrl) return` (silent no-op). Submitting an invalid hostname or duplicate name fails downstream with a toast — destructive in that the form is also reset before the response is verified in some paths (`resetConfigForm()` runs only on success, but the lack of inline `aria-invalid`+message means users guess). | Add inline field-level validation on blur (URL pattern, name uniqueness via `/api/services` GET), disable Save until valid, keep form contents on error. |
| 4 | H4 Consistency | HIGH | `index.html:99-101` tabs labelled `Network Scan` / `System` / `Chat` but everywhere else the same surface is called `Discover` (`app.js:909` button text, `app.js:1414` `-- select services in Discover --`, `app.js:1670` `run Discover first`). User has to translate "Network Scan" ↔ "Discover" mentally. | Pick one term project-wide (`Scan` per the protocol-first reframe in `RUN_BRIEF_MAY03.md`) and replace the other across HTML + JS strings. |
| 5 | H6 Recognition over recall | HIGH | `index.html:284-286` Service `<select>` uses sentinel labels like `-- scan first --`, `-- select services in Discover --`, `-- discover first --` (`app.js:1410`, 1414, 1498) — three near-identical disabled options that demand the user remember which page does what. The Auto-route option `⊛ Auto-route` (`app.js:1459`) is also unlabelled — no tooltip explaining that it delegates to brutus circuit-breaker logic in `server.ts:292`. | Replace sentinel-as-instruction with a small banner above the chat input ("No services yet — run Scan on the Network Scan tab") with a deep-link button; add `title` on the Auto-route option describing failover behavior. |

Hardener can begin on items 1–5 immediately; the rest of the pass below adds another ~25 items spread across the 10 heuristics.

---

## H1 — Visibility of system status

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 1.1 | HIGH | `Web-UI/index.html:110`, `app.js:870-913` | Discover/Scan button has no in-flight progress beyond a text swap; user cannot tell whether the 3 s `SCAN_MS` wait (`server.ts:6`) is hung or working. | Inline spinner + "found N" live counter; expose partial results as they arrive. |
| 1.2 | MED | `app.js:888-905` | After scan, services are *also* probed for `/api/models` reachability, but the only feedback for unreachable services is a 5 s toast (`app.js:904`). When the toast disappears, the service list shows status `unreachable` (`app.js:895`) but the badge styling for that state is not defined in the visible CSS — likely renders as default. | Add a dedicated `.status-unreachable` style (orange) and a permanent inline note next to each unreachable item. |
| 1.3 | MED | `index.html:404-405` System tab | `system-status` text reads `● idle` regardless of actual state until something writes to it. No "last scan at HH:MM:SS" or "health poll: 2 s ago". | Add timestamp + auto-tick the health-poll status; mirror the 20 s loop from `server.ts:71-84`. |
| 1.4 | MED | `app.js:1289-1290` `streamState`/`activeController` | Chat send does not surface streaming state in the UI besides a pulsing cursor (`app.js:1394`). User cannot see "connected to backend X / model Y" before tokens arrive — the response header `X-Saturn-Service` (`server.ts:349`) is set but never read in `app.js`. | Read `X-Saturn-Service`/`X-Saturn-Model` response headers and display "Routed via <service>/<model>" badge on the assistant bubble. |
| 1.5 | LOW | `index.html:362-389` chat input | No character / token counter near the textarea even though `TOKEN_BUDGET = 100000` (`app.js:1292`) is enforced. The context bar (`index.html:358`) is below the messages, easy to miss. | Add a tiny `~Nk / 100k` indicator inside the input chrome. |
| 1.6 | LOW | `index.html:467` Remote tab | `proxy-tunnel-status` reads `● stopped` until a tunnel starts, but the cloudflared spawn (`server.ts:111-143`) can take up to 30 s. No progress feedback. | Show "starting tunnel… (cloudflared)" with elapsed timer. |

## H2 — Match between system and the real world

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 2.1 | HIGH | `index.html` everywhere | Brief explicitly mandates protocol-first language. Current copy speaks of "services" and "Saturn" as a thing the UI owns rather than as `_saturn._tcp.local.` peers (e.g. welcome examples `index.html:336` "What is Saturn?"). | Add a one-line subtitle to the Network Scan tab: "Browsing `_saturn._tcp.local.` over mDNS" so the protocol identity is exposed. (Writer owns copy; geoff flags location.) |
| 2.2 | MED | `app.js:1290-1395` `<think>` parsing | Toggle reads `Thinking… (click to expand)` (`app.js:1389`). Users who don't know about Ollama/DeepSeek-R1 reasoning blocks won't recognize the term; "model's reasoning" is more universal. | Rename to `Model reasoning (click to expand)`. |
| 2.3 | MED | `index.html:113-117` admin gate | Field labelled simply "Admin / password / Unlock" — no indication this admin password is the auto-generated one printed in the bun console (`server.ts:8-18`). First-run users hit a wall. | Hint text under the field: "Printed once in the server console on first run; set `SATURN_ADMIN_PASSWORD` to override." |
| 2.4 | LOW | `index.html:142-144` Deployment options | "Cloud (remote API)" vs "Local (machine running local AI service)" — users speak Ollama/OpenRouter, not "deployment". | Rename options "Hosted API (OpenRouter, OpenAI, …)" and "Local machine (Ollama, llama.cpp, …)". |
| 2.5 | LOW | `app.js:1424` alias prefix | Aliases shown as `@ name` in the dropdown — works for chat fluency but `@` is overloaded (mentions, env vars). | Use a label group `<optgroup label="Aliases">` instead of glyphs. |

## H3 — User control and freedom

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 3.1 | HIGH | `index.html:264` `clear-chats-btn` "Delete History" | One-click destructive — `app.js` (search shows no `confirm()` near this id) deletes all chats with no undo and no confirmation dialog. localStorage is non-recoverable. | Two-step confirm (modal with chat count) + undo toast that re-stages the JSON for ~10 s before purge. |
| 3.2 | MED | `app.js:1287-1290` chat sending | No visible "Stop" button on streaming responses despite `activeController = AbortController` machinery (`app.js:1290`). | Wire a Stop button to `activeController.abort()` while `sending === true`; reuse the `.btn-stop` class from `index.html:951`. |
| 3.3 | MED | `index.html:587-940` config overlay | The huge sampling/engine settings sheet has only "Reset All" (`index.html:936`) — no per-row revert beyond the small "Default" toggle. Once a user starts touching sliders, partial changes are easy to lose if they hit Reset All. | Add per-section "Reset section" buttons; warn before "Reset All". |
| 3.4 | MED | `app.js:1033-1042` Configure New Service flow | Replaces `discover-main` with `config-page` (full takeover, not a modal). Browser back button will exit Saturn entirely instead of returning to Discover. | Push a hash state (`#configure`) so `popstate` returns to the prior view. |
| 3.5 | LOW | `index.html:223` `cfg-back` button | Says only "Back". User who came in from the discover tab via the start-button auto-redirect (`app.js:988`) has no breadcrumb. | Label "Back to Network Scan" + breadcrumb at top of config page. |

## H4 — Consistency and standards

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 4.1 | HIGH | tabs vs body copy | `Network Scan` ↔ `Discover` mismatch (see Top-5 #4). |
| 4.2 | MED | `index.html:489-518` connector cards | Card hint text mixes register: `JSON config`, `TOML config`, `Settings GUI`, `Needs proxy`, `Env vars`. "Needs proxy" tells users *what's missing*, while the others tell *what to do*. | Normalize to "<format> · <action>" pattern: `JSON · Edit config`, `GUI · Settings panel`, `CLI · Run one-liner`, `Proxy · saturn-bridge`, etc. |
| 4.3 | MED | button styles | Three button classes in use — `.btn`, `.btn-secondary`, `.btn-stop` — but several inline styles override them (`index.html:121`, `525`, `544`). Visual hierarchy of primary vs secondary is inconsistent across pages. | Remove inline `style="padding…"` on buttons; introduce `.btn-sm` / `.btn-tertiary` if needed. |
| 4.4 | MED | `index.html:113-122` admin gate vs `index.html:436-457` remote gate | Both are gates with identical purpose (warning + click-through accept), but the admin gate uses an inline form and the remote gate uses a `.gate` block with SVG. Different shape, different microcopy ("Unlock" vs "I Understand — Enable Remote Access"). | Use one shared `.gate` component for both. |
| 4.5 | LOW | `app.js:909` button text reverts to `Discover` while `index.html:110` is `Network Scan` | Even within one button, the resting label disagrees with itself. | Single source-of-truth for label string. |
| 4.6 | LOW | mixed glyph use | `⊙`, `⊛`, `◇`, `★`, `☆`, `▊`, `─` (`app.js:1395, 1435, 1448, 1459, 1597, 1591`). These don't map to a system; users can't tell why some services have `⊙` and aliases `@`. | Document or remove the glyph taxonomy. |

## H5 — Error prevention

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 5.1 | HIGH | `app.js:1089-1129` Save | See Top-5 #3 — silent return on missing fields, no name uniqueness check, no URL validation beyond the implicit `cfg-base-url` text input. |
| 5.2 | MED | `index.html:175` Port field | `type="number"` with no min/max; valid TCP ports are 1-65535. Lets user submit `0` or `999999`. | Add `min=1 max=65535`. |
| 5.3 | MED | `index.html:165` API key field | Plain `type="password"` — no warning that the key is sent to localhost (`server.ts`) and may be persisted in service config files. | Inline note: "Key is stored on this machine. Use Ephemeral Keys for short-lived access." |
| 5.4 | MED | `index.html:262` "+ New" chat button | Discards an in-progress streaming response if pressed mid-generation (no guard found in `app.js`). | Disable while `sending === true` or confirm. |
| 5.5 | LOW | `app.js:1141` ephemeral defaults | `rotation_interval=300`, `expiration_interval=600` are seconds but the labels (`index.html:207`, `212`) don't say `(seconds)`. Easy to set a "5" thinking minutes. | Add unit suffix to label and `min=5`. |
| 5.6 | LOW | `index.html:628` model filter | Free-text input parsed by `lobechat`-style syntax `-all,+gpt-4o`. Typos silently apply. | Live-validate and show resulting visible-models count. |

## H6 — Recognition rather than recall

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 6.1 | HIGH | service select sentinel options | See Top-5 #5. |
| 6.2 | MED | `index.html:482-518` connector grid | Cards show only the tool name + format. User cannot recall which tool they configured last. | Mark cards with a check-badge once the user has copied credentials for that tool (persist in localStorage). |
| 6.3 | MED | `index.html:601-604` config scope | "Global Defaults" vs "Per-Service" toggles; once you pick Per-Service the dropdown appears (`index.html:601`) but the heading does not change to reflect *which* service you're editing. | Show "Editing: <service>" sticky banner. |
| 6.4 | MED | `index.html:660-693` config rows | Each row has a "Default" toggle button and a hidden `.param-controls`. Until you click "Default" you don't know whether this row is *currently* at default or has been overridden — the button label is the same either way. | Toggle should read `Default` when at default, `Override · click to revert` when changed; or use a clear pill state. |
| 6.5 | LOW | `index.html:284` service `<select>` | Only the name is visible. Priority, deployment, model count are all hidden until you pick. | Multi-line option text or a status panel below the select. |
| 6.6 | LOW | `index.html:381` Tools FAB | Wrench glyph only, tooltip "MCP Tools". Users won't know what MCP is on first sight. | Add a once-only inline help bubble on first tab visit. |

## H7 — Flexibility and efficiency of use

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 7.1 | MED | chat input | No keyboard hint visible. Send-on-Enter vs Shift+Enter behavior is not announced anywhere in `index.html` or `app.js` (search). | Add a tiny `Enter to send · Shift+Enter for newline` muted hint under the textarea. |
| 7.2 | MED | no global shortcuts | Tabs (`index.html:99-101`) cannot be activated by `g d` / `g s` / `g c` or `Cmd+1/2/3`. | Wire keyboard shortcuts; add a `?` modal listing them. |
| 7.3 | MED | `index.html:262` history drawer | No search across past chats; with `MAX_CHATS = 50` (`app.js:1225`) the list grows long and is keyboard-unreachable. | Filter input at top of `#history-list`. |
| 7.4 | LOW | `index.html:296-302` style select | Three named styles — Default / Concise / Detailed / Code. No way to save custom system prompt as a quick-pick. | Allow user-defined entries pulled from Presets (`index.html:651`). |
| 7.5 | LOW | `index.html:373-378` export buttons | JSON / Markdown export are FABs with icon-only buttons; power users will want a `Cmd+E` shortcut. | Add accelerator. |

## H8 — Aesthetic and minimalist design

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 8.1 | HIGH | `Web-UI/index.html:8-26` body grain + `styles.css:55-69` CRT scanlines + `app.js:438-442` `FilmGrainShader` + `app.js:441` `ChromaticAberrationShader` + `app.js:78-85` vignette | Five overlapping global "atmosphere" filters (DOM grain, CSS scanlines, WebGL grain, chromatic aberration, vignette). Combined opacity is enough to *measurably* reduce text contrast on the System dashboard and reduce perceived sharpness on the chat output. Brutalist ≠ illegible. | Keep brutalist mono + heavy borders; drop CRT scanlines and DOM grain on text-heavy pages (chat, system). Limit shader effects to the 3D Saturn canvas only. |
| 8.2 | HIGH | brightness — Saturn-gww.1 | `app.js:435` UnrealBloom strength `1.8` + threshold `0.55` is the source of the "Saturn ring is too bright" complaint in the brief. Note also `BrightnessClampShader uMax=1.2` (`app.js:334`) — the clamp runs *before* bloom, so bright golds bloom anyway. | Lower strength to ~0.9, raise threshold to ~0.75, or move clamp post-bloom. (Owned by demo on Saturn-gww.1; flagged here for completeness.) |
| 8.3 | MED | `index.html:587-940` config overlay | 30+ sampling parameters with sliders and number inputs in a single scroll. Most users will never touch Mirostat or TFS Z. | Collapse "Advanced Sampling" by default (already a `<details>`, good) but also collapse "Sampling" and group by "common / advanced" with a simple/expert toggle. |
| 8.4 | MED | `index.html:362-389` chat input fabs | Six floating FABs (clip, thinking, JSON export, MD export, tools, send). Visual noise for a single textarea. | Group export under one "Export ▾" menu; move thinking-toggle into a dropdown. |
| 8.5 | LOW | `styles.css:13-15` font-muted vs font | `--fg-muted: rgba(255,255,255,0.6)` and `--fg: rgba(255,255,255,0.7)` differ by 0.1 alpha — visually indistinguishable on `#000`. The "muted" intent is lost. | Tighten muted to ~0.45. |
| 8.6 | LOW | tab indicator (`app.js:262`) | Animated underline plus the already-active tab is filled white (`styles.css:119-123`) — two cues for the same state. | Keep one. |

## H9 — Help users recognize, diagnose, and recover from errors

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 9.1 | HIGH | `app.js:1081` `cfg-test` | See Top-5 #1 — error code overwrites the button label and disappears in 2 s. |
| 9.2 | HIGH | `app.js:982` start/stop service errors | Toast shows `err.detail || 'Operation failed'` for ~3 s and then the button reverts. No log, no diagnostic, no link to backend logs. | Persistent error region under each row; "View log" link to `/api/services/<name>/log` or copy-error-to-clipboard. |
| 9.3 | MED | `app.js:1565-1567` model load error | Error hint shows "Service unreachable" or "Could not load models" with no remediation. | Add "Retry" button + "Open Network Scan" link inside the hint. |
| 9.4 | MED | `app.js:1117, 1121` save service | Toast `err.detail || 'Failed to create service'` — `err.detail` may itself be a generic backend message; the form is left in whatever state the user submitted but no field is highlighted. | Map common backend errors to specific fields (duplicate name → highlight name input, bad URL → highlight base_url). |
| 9.5 | MED | `server.ts:312-316` "No healthy backends available" | The 502 response surfaces in chat as a generic stream error (no specific UX for this case in `app.js`). | Detect 502 + payload `error: "No healthy backends..."` and render a system-bubble with a "Run Scan" button. |
| 9.6 | LOW | `app.js:1233` `loadChats` corrupt JSON | Silent fall-back to empty array; user loses everything without notice. | One-time toast: "Local chat history was corrupt and could not be parsed (saved a backup to <key>)." |

## H10 — Help and documentation

| # | Severity | Where | Issue | Fix |
|---|---|---|---|---|
| 10.1 | MED | `index.html` first-load | No onboarding or "Start Here" affordance. A brand-new user opens the page on the Network Scan tab with a 3D ring, an unlabelled Discover button, and no protocol context. | Add a one-line intro under the Network Scan title: "Saturn advertises `_saturn._tcp.local.` over mDNS. Click Scan to find peers on this network." |
| 10.2 | MED | `index.html:251` Integrate link | Single link to `jperrello.github.io/Saturn/integrations/`. No inline help on the *config form* page (`index.html:127-228`) explaining what each field does. | Add `<small>` hint blocks under each label or a `?` icon that expands. |
| 10.3 | MED | `index.html:626` model filter syntax | "LobeChat-style syntax: `-all,+gpt-4o,+llama3`" — references LobeChat without a link. | Inline expander with examples and the parser grammar. |
| 10.4 | MED | curl / Go examples missing | Per `RUN_BRIEF_MAY03.md` the Web-UI must lead with protocol examples (curl + saturnd) above Python wherever examples appear. The Integrate page (`index.html:478-580`) has tool cards but nothing showing `dns-sd -B _saturn._tcp` or `curl http://<host>:<port>/v1/chat/completions`. | Add a "Try it" code snippet block under the connector grid with curl + saturnd examples. (Writer owns copy; geoff flags location.) |
| 10.5 | LOW | `index.html:957` toast | The single shared toast can stack messages but only shows one at a time and disappears in 3 s. No "View recent notifications" affordance. | Notifications drawer accessible from the topbar. |
| 10.6 | LOW | `index.html:944-953` permission dialog | Dialog says "Tool Call Request" with raw args but no docs link explaining MCP tools or what "Always Allow" persists. | Inline help link. |

---

## Cross-cutting / accessibility (called out, scored under H4/H8)

- **Color contrast** — body text uses `rgba(255,255,255,0.7)` on `#000` (`styles.css:14`). On Mac with the CRT scanline overlay (alpha-stacked rgba(0,0,0,0.12) every 4 px, `styles.css:62-69`) the effective contrast drops below WCAG AA for body copy in some places. Hardener should run a contrast check after disabling scanlines on text-heavy panels.
- **Keyboard navigation** — tabs use `<button>` (good) but `role="tab"` is set only on system sub-tabs (`index.html:399`); top-level tabs lack `aria-selected`/`role`.
- **Focus management** — opening config overlay (`index.html:587`) does not trap focus; tabbing escapes back to the page beneath. Add focus trap.
- **Reduced motion** — `styles.css:38-43` honors `prefers-reduced-motion` for CSS, but the WebGL bloom + animated stars + chromatic aberration in `app.js:408+` continue regardless. Gate the `composer.render()` shader passes on a `prefers-reduced-motion` media query.

## Items deferred (not Web-UI surface)

- Server-side observability (`server.ts:71-84` health loop) does not expose state to the UI beyond `health` map; H1.3 fix depends on a new endpoint — file under hardener if it touches `server.ts`, otherwise defer.
- mDNS protocol-level errors (e.g. multicast disabled on the interface) are silent in `server.ts:153-204` `discover()`. Surfacing those is a server-side change.

## Verification gap

Browser walk-through could not run this pass (Chrome MCP profile locked by parallel session). Hardener should:
1. Open `http://localhost:3000` in Playwright.
2. Reproduce items 1.1, 1.2, 3.1, 5.1, 9.1, 9.2 by triggering the failure paths.
3. Run `tests/bombadil/run.sh` after any `Web-UI/` or `saturn/web.py` change (per memory).
