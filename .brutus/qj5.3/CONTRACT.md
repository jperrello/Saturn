# CONTRACT: Saturn-qj5.3 — MCP TOOLS popup + intuitive Add-MCP flow

Bead: Saturn-qj5.3 (P1)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-qj5.3` + RUN_BRIEF_MAY04.md Bucket 1 item #3.

## Spec restatement
Today the chat tab carries an inline persistent panel `#tools-panel` (`Web-UI/index.html:314-330`) holding MCP tools, the non-obvious `#tools-manage` ("Servers") button, and a hidden `#mcp-servers-config` sub-block whose name/url/token form is reachable only by a second click. The MCP entry button `#tools-toggle` (line 382) shows only a wrench SVG with no visible label. The fix:

1. Replace the inline panel with a positioned popup (CSS `position: absolute` or `fixed`), matching the qj5.2 popup pattern.
2. The MCP entry button must show visible `MCP` or `Tools` text — discoverable on screen, not just via aria/title (Nielsen H6).
3. The "Add MCP server" affordance must appear inside the popup directly when it opens — no `Servers` sub-click required to reveal the add form.

Falsifier: button has no visible MCP/Tools text label, OR clicking the entry does not produce a positioned popup whose immediate visible content surfaces an `Add MCP server` / `+ MCP server` / `New MCP …` affordance.

## Test files
- `saturn/tests/test_chat_ux_qj5_3.py` (new, 2 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium, viewport 1400×900)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_3.py --timeout=60 -v
```

## Captured red output (full transcript at `.brutus/qj5.3/transcript.md`)
```
collected 2 items

saturn/tests/test_chat_ux_qj5_3.py::test_mcp_entry_button_has_visible_label  FAILED
saturn/tests/test_chat_ux_qj5_3.py::test_mcp_click_reveals_popup_with_add_server  FAILED

E   AssertionError: no chat-tab button shows visible 'MCP' or 'Tools' text. visible labels: [...]
                    aria-label / title alone do not satisfy Nielsen H6.
E   AssertionError: after MCP click, no positioned (absolute/fixed) popup surfaces a discoverable
                    'Add MCP server' / '+ MCP server' / 'New MCP …' affordance directly. The
                    current #tools-panel is inline (not positioned) and hides the add form
                    behind a 'Servers' button.

========================= 2 failed, 1 warning in 18.81s =========================
```

## Oracle definition

Module-scoped fixture: same as qj5.2 (real `python3 -m saturn web` via harness, headless Chromium 1400×900, chat tab activated, gate dismissed with JS-click fallback).

1. **`test_mcp_entry_button_has_visible_label`** — across `#chat-shell button, .chat-topbar button`, at least one *visible* button has `inner_text()` (lower-cased, stripped) containing `mcp` or `tools`. aria-label / title do NOT satisfy.

2. **`test_mcp_click_reveals_popup_with_add_server`** — picks the in-viewport button whose combined text/aria-label/title (lower-cased) matches `/mcp|tools/`, clicks it via `el.click()` in JS-evaluate. After 500 ms, walks the DOM and finds a visible element with `getComputedStyle().position ∈ {absolute, fixed}` whose own `innerText` (lower-cased, < 4000 chars) matches at least one of `/add\s+mcp/`, `/add\s+server/`, `/\+\s*mcp/`, `/\+\s*server/`, `/new\s+mcp/`. That element is the popup; its existence satisfies the oracle.

## Out of scope (do NOT touch / explicitly NOT asserted)
- The exact form fields inside the add-server flow (name/url/token are the existing `#mcp-name` / `#mcp-url` / `#mcp-token`; keep, restyle, or rename — not asserted).
- Backing /api/mcp/servers behaviour — qj5.16.2 already gates it server-side; no change here.
- Settings popup from qj5.2 — must continue to satisfy its own contract.
- The `+ menu` over the chat input — qj5.4's territory.
- Edit-sent-message — qj5.6's territory.
- Existing 16.1 / 16.2 / 16.10 / 8v5 / 16.6+.7 / qj5.1 / qj5.2 suites — must stay green.

## Acceptance
1. Both tests in `saturn/tests/test_chat_ux_qj5_3.py` go green.
2. `pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_chat_ux_qj5_2.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py` continues to pass.
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations.
5. Visual: rodney screenshot at `demo/recordings/qj5.3.png` shows the labeled MCP entry and the popup with its Add-MCP affordance — captured and narrated by demo per scaffold.

## Implementer
hardener (per athena routing — same chain through qj5.2 6461641)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.3/transcript.md`
