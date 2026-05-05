# CONTRACT — Saturn-ao6 (cbt.2.d): edit-and-regenerate flake

**Status:** RED. Test authored, two real flakes found, fix routed to
hardener as **Saturn-bny** (P1).

The bead is closed because the **test deliverable is complete**: I shipped
the falsifiable harness that detects the flake. The fix is a separate
work item belonging to a code lane (hardener), not bombadil.

## Spec restatement (5 prongs, falsifiable)

`tests/bombadil/edit_ao6.py` checks these invariants against the live
Web-UI on `$SATURN_PORT` driving real Ollama via the auto-injected
`__manual__:local` endpoint:

| Prong | Invariant | Result |
|-------|-----------|--------|
| A | Rapid Edit clicks (5 in a row) produce exactly 1 `.edit-textarea` (idempotency guard at `Web-UI/app.js:4250`). | **PASS** |
| B | Edit → cancel → re-edit cleanly restores a `.bubble` div and re-opens a fresh textarea. | **PASS** |
| C | Edit → Save & regenerate: after new stream completes, `chat.messages.length` (localStorage `saturn-chats[0].messages`) MUST equal `#messages .msg` count, AND the last user message in storage must contain the edited text. | **FAIL** — DOM=3, stored=2 (orphan userDiv left behind by save handler at `app.js:4283-4302`; `send()` then creates a duplicate user div). |
| D | Mid-stream edit attempt: while a stream is in flight, opening the editor and clicking Save MUST NOT diverge DOM and storage after the in-flight stream settles. | **PASS** (counts match at 1, but see note below — this is a degenerate "both happen to equal 1 because save bailed and stream lost its placeholder" pass; weaker signal than C). |
| E | Edit-with-attachment present: the regenerated user message in storage must contain the `--- File: <name> ---` marker AND the edited text, AND DOM/stored counts must match. | **FAIL** — file marker IS inlined correctly (good — `attachedFile` survived to `send()`), but the same orphan-userDiv bloat from prong C corrupts DOM/stored equality. |

## Test file

`tests/bombadil/edit_ao6.py`

## Run command

```
SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/edit_ao6.py
```

Requires saturn web on `$SATURN_PORT` and Ollama with `qwen2.5:0.5b`.
Wall time: ~3 min (D prong does a 60s+ long stream).

## Captured RED run (verbatim summary)

```
{
  "oracle": {
    "A_rapid_clicks_idempotent": true,
    "B_cancel_reedit_clean": true,
    "C_edit_save_consistent": false,
    "D_midstream_no_drift": true,
    "E_attachment_inlined_on_edit": false
  },
  "js_errors": [],
  "pass": false
}
```

Full results with per-prong fields: `.brutus/Saturn-ao6/result.json`.

## Root cause (handed to hardener)

`Web-UI/app.js:4283-4302` (save handler in `beginEdit`):

1. Replaces the `.bubble` inside the original `userDiv` with a new
   `.bubble` containing the edited text — BUT leaves the userDiv itself
   in the DOM.
2. Removes following sibling `.msg` elements (the old assistant) and
   splices `chat.messages.length = idx` (drops user too).
3. Calls `send()` with `input.value = newText`.
4. `send()` at `app.js:2050+` pushes a new user message to
   `chat.messages` AND appends a brand-new `.msg.user` div to `#messages`.

Net: DOM gets `[orphan_userDiv, new_userDiv, new_assistant]` while
storage gets `[new_user, new_asst]`. Visually the user's edited text
appears twice.

Two clean fixes (hardener picks):
- **Drop the orphan**: in the save handler, `userDiv.remove()` before
  invoking `send()`. Storage and DOM stay aligned because send() will
  recreate the user msg from scratch.
- **Reuse the existing div**: have `beginEdit` save handler call a
  `send()` variant that pushes to `chat.messages` and starts the
  assistant placeholder WITHOUT creating a fresh userDiv (i.e. accept
  the existing userDiv as the user message DOM node).

Filed as **Saturn-bny** (P1, route hardener).

## Why no fix in this attestation

Bombadil lane authors and runs the test, identifies the flake, and routes
the fix. Touching the Web-UI render/send path is hardener's lane.

## Related

- Parent: Saturn-cbt.2.d
- Sibling tests in this run: Saturn-3t8 (cbt.2.a.ui), Saturn-6g1 (cbt.2.b)
- Fix bead: **Saturn-bny**

## Bead

Saturn-ao6 — closed. Test shipped + flake located + fix bead filed.
