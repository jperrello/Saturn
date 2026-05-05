# CONTRACT: Saturn-qj5.1 — remove top-right response-style pill from Chat tab

Bead: Saturn-qj5.1 (P1)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-qj5.1` + RUN_BRIEF_MAY04.md Bucket 1 item #1.

## Spec restatement
The four-option response-style pill rendered at `Web-UI/index.html:299-304` (`<select id="style-select">` with options `Default / Concise / Detailed / Code`) lives in `.strip-right` at the top-right of the Chat tab. It must be removed from that location. Style selection relocates to the per-chat Settings popup — that relocation is **qj5.2's** scope and is *not* asserted here. This contract closes only the removal half. Falsifier: the pill (under any id, in any select shape) still surfaces inside the chat-strip top-right region.

## Test files
- `saturn/tests/test_chat_ux_qj5_1.py` (new, 2 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium via `playwright.sync_api`)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_chat_ux_qj5_1.py -v
```
(The PATH prefix matters when re-running under `showboat exec` — uvx's bundled `python3` shadows the saturn-bearing system python, breaking the harness's `subprocess.Popen(["python3", "-m", "saturn", ...])`. Plain `python3 -m pytest …` works in a normal shell.)

## Captured red output (full transcript at `.brutus/qj5.1/transcript.md`)
```
collected 2 items

saturn/tests/test_chat_ux_qj5_1.py::test_style_pill_removed_by_id      FAILED
saturn/tests/test_chat_ux_qj5_1.py::test_no_style_select_in_top_strip  FAILED

E   AssertionError: #style-select still present in DOM — pill was not removed
E   AssertionError: top-strip <select> still exposes the response-style pill options:
        [['default', 'concise', 'detailed', 'code']]

========================= 2 failed, 1 warning in 8.23s =========================
```

## Oracle definition

Module-scoped fixture: spin up `tests.harness.web.serve()` (real `python3 -m saturn web`), launch headless Chromium via `playwright.sync_api`, navigate to `srv["origin"]`, click the `[data-tab="chat"]` tab if present, wait for `networkidle`. Assertions against the live DOM:

1. **`test_style_pill_removed_by_id`** — `page.query_selector("#style-select")` returns `None`. The legacy id from index.html:299 must not exist anywhere on the page.
2. **`test_no_style_select_in_top_strip`** — for every `<select>` matching `.strip-right select, .chat-strip select`, the lower-cased text of its `<option>` children does NOT form a superset of `{"default", "concise", "detailed", "code"}`. Catches the "renamed select, same place" non-fix.

## Out of scope (do NOT touch / explicitly NOT asserted)
- **Adding the style picker to the per-chat Settings popup** — that is qj5.2's contract. This bead asserts only removal.
- **Replacing `<select>` with a 4-button group inside `.strip-right`** — would technically pass both assertions today (vacuous) but violates the spirit of the bead (relocation, not relabeling). Reviewer to flag visually; I am not encoding this as a falsifier here because it would require a passes-on-first-run guardrail (forbidden by Brutus discipline).
- Server-side `style` parameter handling on `/api/chat` and `/api/proxy/chat` — keep as-is; UI-side relocation only.
- Other chat-tab strip elements (service / model selectors, settings cog, models/tools panels) — must keep working; no regression in Bombadil `chat.ts` spec or `tests/harness/selftest.py`.
- Existing 16.1 / 16.2 / 16.10 / 8v5 / 16.6+.7 auth + proxy suites — must stay green.

## Acceptance
1. Both tests in `saturn/tests/test_chat_ux_qj5_1.py` go green.
2. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py saturn/tests/test_usage_auth.py saturn/tests/test_server_module_auth.py saturn/tests/test_proxy_no_body_keys.py` continues to pass — no regression on shipped contracts.
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations (the chat-tab spec must still drive service/model selection and message send).
5. Visual: rodney screenshot at `demo/recordings/qj5.1.png` shows no pill in the top-right strip — captured and narrated by demo per their existing scaffold.

## Implementer
hardener (per athena routing — same pane that landed fbb5896 / 370f9fa / 3345dbb / 4227474 / 8bf0ef6)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.1/transcript.md`
