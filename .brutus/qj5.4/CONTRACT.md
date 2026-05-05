# CONTRACT: Saturn-qj5.4 — '+' menu replaces 5 unlabeled icons above chat input

Bead: Saturn-qj5.4 (P1)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-qj5.4` + RUN_BRIEF_MAY04.md Bucket 1 item #4 (FINAL menu list verbatim).

## Spec restatement
Today the chat-input row hosts five `.fab` buttons in `<div class="chat-input-fabs">` (`Web-UI/index.html:379-386`):

- `#file-upload-btn` (clip icon — Attach file)
- `#thinking-toggle` (brain icon — Toggle thinking mode)
- `#export-json` (download icon — Export JSON)
- `#export-md` (markdown icon — Export Markdown)
- `#tools-toggle` (wrench icon — MCP Tools)

None has a visible label; all five are illegible/non-descriptive. Replace with a single Claude-style `+` menu next to `#send-btn`. The menu is the FINAL list — exactly two items, do NOT add others:

- Attach file/photo
- MCP tools / Connectors

Style picker is OUT — it lives in the Settings popup (qj5.2). Thinking, export-JSON, export-Markdown are explicitly removed from this surface.

Falsifier: more than one entry-point button remains above the chat input next to `#send-btn`, OR no `+` menu opens, OR the opened menu omits Attach / MCP intent items, OR the menu still surfaces any of the legacy `thinking|export|json|markdown` items.

## Test files
- `saturn/tests/test_chat_ux_qj5_4.py` (new, 2 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium, viewport 1400×900)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_4.py --timeout=60 -v
```

## Captured red output (full transcript at `.brutus/qj5.4/transcript.md`)
```
collected 2 items

saturn/tests/test_chat_ux_qj5_4.py::test_chat_input_row_has_single_entry_button   FAILED
saturn/tests/test_chat_ux_qj5_4.py::test_plus_menu_reveals_only_final_items       FAILED

E   AssertionError: expected at most one entry-point button above the chat input (the '+');
                    found 5. Today the 5 unlabeled .fab icons (...) sit alongside #send-btn.
E   AssertionError: no '+' menu button found in the chat-input area.
                    Visible label '+' (or aria/title 'add menu', 'plus', 'attach menu',
                    'attachments menu') is required so users discover the affordance.

========================= 2 failed, 1 warning in 10.96s =========================
```

## Oracle definition

Module-scoped fixture: same as qj5.2/qj5.3 (real `python3 -m saturn web` via harness, headless Chromium 1400×900, chat tab activated, gate dismissed with JS-click fallback).

1. **`test_chat_input_row_has_single_entry_button`** — count visible `<button>` elements inside `.chat-input-fabs, .chat-input-float, .chat-input-area` excluding `#send-btn`. The count must be ≤ 1.

2. **`test_plus_menu_reveals_only_final_items`** — find a button whose visible text is exactly `+` OR whose `aria-label`/`title` matches `/add\s*menu|plus|attach\s*menu|attachments?\s*menu/`. Click it. After 500 ms, walk the DOM for a *positioned* (`position ∈ {absolute, fixed}`) container with 2–8 visible items (`[role=menuitem], li, button, a` with non-empty text). Smallest such container is the `+` menu. Its item labels (lower-cased) must:
   - include at least one matching `attach|file|photo|upload` (Attach intent),
   - include at least one matching `mcp|connector|tool` (MCP/Connectors intent),
   - contain ZERO matches against `thinking|export|json|markdown` (legacy items must be gone).

## Out of scope (do NOT touch / explicitly NOT asserted)
- Where the `thinking-toggle` behaviour goes after removal — out of this contract; if "thinking mode" persists at all post-fix, it must surface elsewhere (e.g., Settings popup) or be deprecated. Not asserted here.
- Where Export-JSON / Export-Markdown go — same as above. The chat history can keep its export endpoints (`/api/usage/history` etc.) untouched; only the visual entry points are removed from the chat-input row.
- Server-side handlers for file upload, MCP — unchanged.
- The icon shape used inside the `+` button (literal `+` glyph or a plus SVG) — both satisfy as long as the click target's visible text is `+` OR aria/title matches the regex above.
- The exact label text for the two menu items — anything matching the intent regexes is fine ("Attach file" / "Files & photos" / "Upload"; "MCP tools" / "Connectors" / "Tools").
- Settings popup (qj5.2), MCP popup (qj5.3), edit-sent-message (qj5.6) — separate beads.
- Existing 16.1 / 16.2 / 16.10 / 8v5 / 16.6+.7 / qj5.1 suites + qj5.2/qj5.3 once they ship — must stay green.

## Acceptance
1. Both tests in `saturn/tests/test_chat_ux_qj5_4.py` go green.
2. `pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_chat_ux_qj5_2.py saturn/tests/test_chat_ux_qj5_3.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py` continues to pass (assuming qj5.2/qj5.3 already green by then; if not, this contract still must not regress 16.x / 8v5 / qj5.1).
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations. The chat spec must still drive file upload (the path through Bombadil; if `#file-upload-btn` is gone, the harness/spec needs no change — Bombadil only exercises service/model selection and message send today, but watch for regressions).
5. Visual: rodney screenshot at `demo/recordings/qj5.4.png` shows the single `+` button and the two-item menu — captured and narrated by demo per scaffold.

## Implementer
hardener (per athena routing — same chain through qj5.2 6461641; routing held until qj5.2/qj5.3 green per athena's lockstep policy)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.4/transcript.md`
