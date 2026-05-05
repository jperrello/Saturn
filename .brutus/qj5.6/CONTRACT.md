# CONTRACT: Saturn-qj5.6 — edit-sent-message (truncate-and-regenerate)

Bead: Saturn-qj5.6 (P1)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-qj5.6` + RUN_BRIEF_MAY04.md Bucket 1 item #6.

## Spec restatement
Today a sent user message renders as `<div class="msg user"><div class="prefix">&gt; you</div><div class="bubble">…</div></div>` (`Web-UI/app.js:2027-2030`) with no edit affordance. The fix: every rendered `.msg.user` must expose a discoverable Edit affordance. Clicking it puts the message into an editable state populated with the original text. Saving the edit truncates the conversation at that turn (drops the assistant reply and any subsequent turns) and regenerates a fresh assistant reply from the edit.

This contract pins the **first two surfaces** as falsifiable pytest assertions (UI-only, deterministic, no LLM):

1. The `.msg.user` element exposes a visible Edit affordance.
2. Clicking the Edit affordance reveals an editable input (textarea / input / contenteditable) inside the same `.msg.user`, populated with the original message text.

The full **truncate-and-regenerate end-to-end** behaviour (real Ollama, real `/api/chat` round-trip, DOM diff after save: old assistant reply removed, new assistant reply non-empty and differs) is held outside the pytest surface and verified by demo via `tests/harness` + rodney capture per `demo/recordings/qj5.6.md` — see Acceptance item 5. Pytest does not exercise it because (a) it depends on an external Ollama daemon and (b) generation timing makes the test flaky as a contract gate.

Falsifier: any of the two pytest assertions failing OR demo's E2E pass failing to show the truncate-and-regenerate behaviour.

## Test files
- `saturn/tests/test_chat_ux_qj5_6.py` (new, 2 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium 1400×900; module-scoped fixture injects a `.msg.user` element directly into `#messages` so the test surface is the *rendered* user-message DOM)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_6.py --timeout=60 -v
```

## Captured red output (full transcript at `.brutus/qj5.6/transcript.md`)
```
collected 2 items

saturn/tests/test_chat_ux_qj5_6.py::test_user_message_has_edit_affordance                FAILED
saturn/tests/test_chat_ux_qj5_6.py::test_clicking_edit_reveals_editable_input_with_original_text FAILED

E   AssertionError: no Edit affordance inside .msg.user (looked for button/[role=button]/a
                    whose visible text, aria-label, or title contains 'edit'). Today the user
                    message renders only `<div class='prefix'>&gt; you</div><div class='bubble'>…
                    </div>` — the spec requires a way to invoke edit.
E   AssertionError: no Edit button to click inside .msg.user

========================= 2 failed, 1 warning in 12.94s =========================
```

## Oracle definition

Module-scoped fixture: `tests.harness.web.serve()`, headless Chromium 1400×900, chat tab activated, `#chat-accept` gate dismissed (with JS-click fallback). The fixture then **directly injects** a `.msg.user` element matching today's renderer shape into `#messages`, with bubble text equal to `ORIGINAL_TEXT` (`"hello world from brutus qj5.6"`). This bypasses the `send()` early-returns (service/model required) without weakening the contract — the spec is "every rendered user message has Edit," and the assertion is on the rendered-DOM surface.

**Implementer requirement that follows from the test surface:** Edit affordance must attach via event delegation on `.msg.user` (e.g., delegated `mouseenter`/`click` listeners on `#messages`), not solely inside the renderer function. Otherwise the test fixture's injected element won't acquire the affordance and the test stays red. This is also the right architectural choice — chat history reload from `localStorage` re-renders messages, and any per-render handler attachment risks dangling references after re-render.

1. **`test_user_message_has_edit_affordance`** — hover the `.msg.user`. After 200 ms, in JS evaluate, scan its descendants for any `button`, `[role=button]`, or `a` whose combined `(innerText + aria-label + title)` (lower-cased) matches `\bedit\b`. At least one must exist.

2. **`test_clicking_edit_reveals_editable_input_with_original_text`** — hover `.msg.user`, find the same Edit affordance, click it. After 300 ms, scan `.msg.user` descendants for `textarea`, `input[type=text]`, `input` (no type), `[contenteditable=""]`, `[contenteditable="true"]`. At least one must hold (`.value` for inputs, `.innerText` for contenteditable) the literal string `ORIGINAL_TEXT`.

## Out of scope (do NOT touch / explicitly NOT asserted in pytest)
- The exact look of the Edit affordance (icon vs. text vs. menu) — anything matching the regex satisfies.
- Hover-revealed vs. always-visible — both satisfy as long as the affordance is in the DOM after the test's hover.
- The save / cancel control names and shapes — not asserted; demo's rodney capture is the visual gate.
- Truncate-and-regenerate semantics — verified by demo's E2E flow against real Ollama (see Acceptance #5). Skipping in pytest because Ollama generation timing is non-deterministic and would make the contract gate flaky.
- `chats[activeChat].messages` mutation shape on save — implementer's choice; the user-visible DOM after save is what matters and demo verifies it.
- Existing 16.1 / 16.2 / 16.10 / 8v5 / 16.6+.7 / qj5.1 / (qj5.2 / qj5.3 / qj5.4 once they ship) suites — must stay green.

## Acceptance
1. Both tests in `saturn/tests/test_chat_ux_qj5_6.py` go green.
2. `pytest saturn/tests/test_chat_ux_qj5_1.py saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py` continues to pass (plus qj5.2/qj5.3/qj5.4 once they ship).
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations.
5. **Demo E2E gate (visual + behavioural):** demo runs `tests/harness/run.sh` with the qj5.6 flow against real Ollama (`qwen2.5:0.5b`):
   - Send "what is the capital of France?" → wait for assistant reply with non-empty text.
   - Click Edit on the user message, change text to "what is the capital of Germany?", save.
   - Within 30 s, the original assistant reply is gone from the DOM and a new assistant reply appears.
   - The new assistant reply text differs from the captured original (case-insensitive substring match: original mentions "paris", new mentions "berlin"; if the model is wrong, the looser invariant is "new text != original text").
   - rodney captures `demo/recordings/qj5.6.png` showing the post-edit state.

## Implementer
hardener (per athena routing — same chain through qj5.2; routing held until upstream chat-UX beads green per athena's lockstep policy)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.6/transcript.md`
