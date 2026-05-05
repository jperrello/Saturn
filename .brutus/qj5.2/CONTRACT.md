# CONTRACT: Saturn-qj5.2 — Saturn SVG → labeled Settings button + per-chat popup

Bead: Saturn-qj5.2 (P1)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-qj5.2` + RUN_BRIEF_MAY04.md Bucket 1 item #2.
Lands the relocation that qj5.1 (closed at 6461641) deliberately deferred.

## Spec restatement
The non-discoverable Saturn-ring SVG that today renders inside `<button class="chat-settings-btn …">` at `Web-UI/index.html:268` (drawer) and `:297` (strip) must be replaced by a clearly-labeled Settings button — discoverable by reading, not just by hovering for the title/aria. Clicking that button opens a per-chat popup containing all three control families:

- Response style options: Default / Concise / Detailed / Code (the four labels relocated from the qj5.1 strip-right pill).
- Per-chat model override.
- Current Saturn service.

Falsifier: no chat-tab button shows visible `Settings` text, OR the click does not reveal a single visible container that holds all four style option labels alongside a model and a service control.

## Test files
- `saturn/tests/test_chat_ux_qj5_2.py` (new, 2 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium via `playwright.sync_api`, viewport 1400×900)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_2.py --timeout=60 -v
```

## Captured red output (full transcript at `.brutus/qj5.2/transcript.md`)
```
collected 2 items

saturn/tests/test_chat_ux_qj5_2.py::test_chat_settings_button_has_visible_label_text     FAILED
saturn/tests/test_chat_ux_qj5_2.py::test_settings_click_reveals_popup_with_required_contents FAILED

E   AssertionError: no chat-tab button shows visible 'Settings' text. visible labels: [...]
                    Nielsen H6 (recognition not recall) requires the label, not just aria/title.
E   AssertionError: after Settings click, no visible container holds all 4 style options
                    (Default / Concise / Detailed / Code). The popup is missing.

========================= 2 failed, 1 warning in 15.23s =========================
```

## Oracle definition

Module-scoped fixture: `tests.harness.web.serve()` (real `python3 -m saturn web`), headless Chromium with viewport 1400×900, chat tab activated, `#chat-accept` gate dismissed if visible (with JS-click fallback for offscreen layouts).

1. **`test_chat_settings_button_has_visible_label_text`** — across `.chat-shell button, .chat-drawer button, .chat-topbar button`, at least one *visible* button has `inner_text()` (lower-cased, stripped) containing the substring `settings`. The aria-label / title attribute does NOT count — Nielsen H6 requires the label be readable on screen.

2. **`test_settings_click_reveals_popup_with_required_contents`** — picks the `.chat-settings-btn` whose `getBoundingClientRect()` lies inside the current viewport (drawer instances positioned via transform are skipped). Clicks it via `el.click()` in JS-evaluate (bypasses Playwright's strict viewport gate so the test reflects user intent, not framework idiom). After a 500 ms settle, finds the smallest visible element whose own `innerText` (case-insensitive) contains all four of `default`, `concise`, `detailed`, `code`. That element is the popup container. Its text must additionally match `/model/` AND `/(service|saturn)/`.

## Out of scope (do NOT touch / explicitly NOT asserted)
- The shape of the per-chat model override (free-text vs. select vs. autocomplete) — any control labelled with the word `model` inside the popup container satisfies the oracle.
- The shape of the service indicator (read-only label vs. dropdown switcher) — any visible text containing `service` or `saturn` inside the popup container satisfies the oracle.
- Settings page (`#settings-page`) — that is the existing non-popup path, untouched.
- MCP TOOLS popup, the `+` menu, the file-upload affordance — qj5.3 / qj5.4 / qj5.5 / qj5.6 territory.
- Any other `.chat-settings-btn` reference (e.g., in tests/) — keep as-is unless directly affected.
- Existing 16.1 / 16.2 / 16.10 / 8v5 / 16.6+.7 / qj5.1 suites — must stay green.

## Acceptance
1. Both tests in `saturn/tests/test_chat_ux_qj5_2.py` go green.
2. `pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py` continues to pass — no regression on shipped contracts.
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations (the chat spec must still drive service/model selection and message send; if the strip layout changes, Bombadil extractors `serviceSelect` / `modelSelect` must still resolve).
5. Visual: rodney screenshot at `demo/recordings/qj5.2.png` shows the labeled Settings button and the popup contents — captured and narrated by demo per the existing scaffold at `demo/recordings/qj5.2.md`.

## Implementer
hardener (per athena routing — same pane that landed fbb5896 / 370f9fa / 3345dbb / 4227474 / 8bf0ef6 / 6461641)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.2/transcript.md`
