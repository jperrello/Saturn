# RE-ATTESTATION — Saturn-ao6 after Saturn-bny green

**Verdict on bny-targeted scope:** **GREEN.** Prongs C and E now both PASS.
**Residual finding:** prong D (mid-stream edit) still RED — out of bny
scope, filed separately as **Saturn-9ha** (P2).

## What changed

Hardener landed `Web-UI/app.js:4277` (commit `417ba93` on
`autonomous/promo-push`): the save handler now calls `userDiv.remove()`
before calling `send()`, so no orphan user div lingers in the DOM.

## Re-run

```
SATURN_ADMIN_PASSWORD=… SATURN_ADMIN_TOKEN=…(32+) SATURN_RUNNER_TOKEN=…(32+) \
  python3 -m saturn web --port 39301 &

SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/edit_ao6.py
```

## Result (verbatim, post-bny)

```
{
  "results": {
    "A_rapid_clicks_one_textarea": true,
    "B_cancel_then_reedit": true,
    "C_edit_save_happy": {
      "before_dom": 2, "before_stored": 2,
      "after_dom":  2, "after_stored":  2,
      "last_user_matches_edit": true,
      "dom_eq_stored": true,
      "no_js_errors": true
    },
    "D_midstream_edit": {
      "streaming_when_edit_clicked": true,
      "edit_textarea_opened": true,
      "save_invoked": true,
      "final_dom": 0, "final_stored": 1,
      "dom_eq_stored": false,
      "no_js_errors": true
    },
    "E_edit_with_attachment": {
      "badge_was_visible": true,
      "stored_user_has_file_marker": true,
      "stored_user_has_edit_text": true,
      "dom_eq_stored": true,
      "no_js_errors": true
    }
  },
  "oracle": {
    "A_rapid_clicks_idempotent": true,
    "B_cancel_reedit_clean": true,
    "C_edit_save_consistent": true,
    "D_midstream_no_drift": false,
    "E_attachment_inlined_on_edit": true
  },
  "js_errors": [],
  "pass": false
}
```

Saved JSON: `.brutus/Saturn-ao6/result-postbny.json`.

## Per-prong delta vs. original RED run

| Prong | Pre-bny | Post-bny | Notes |
|-------|---------|----------|-------|
| A | PASS | PASS | unchanged |
| B | PASS | PASS | unchanged |
| C | **FAIL** (DOM=3, stored=2) | **PASS** (DOM=2, stored=2) | bny fix |
| D | "PASS" (degenerate, both=1) | **FAIL** (DOM=0, stored=1) | now exposed cleanly — see below |
| E | **FAIL** (DOM bloat) | **PASS** (file marker + edit text both preserved, counts match) | bny fix |

The D regression-from-PASS-to-FAIL isn't a regression — bny removed the
mask. Pre-bny, the orphan userDiv masked D as DOM=1 happening to equal
stored=1 by coincidence. Post-bny, with no orphan, the real residual
drift surfaces: when save fires mid-stream, send() bails (existing
`sending` guard), but the original stream's assistant placeholder was
already removed from DOM by the save handler's sibling-remove loop. The
in-flight stream completes and pushes an assistant to chat.messages
(stored=1) with no DOM peer (DOM=0).

## Saturn-9ha (filed for hardener)

P2. Two fix options handed over:
- **(a)** disable the Save button while `sending===true` (cheap, safe)
- **(b)** call `activeController.abort()` from the save handler before
  invoking `send()` (richer — actually re-runs the requested edit)

Test reproduces deterministically every run; reuses prong D of
`tests/bombadil/edit_ao6.py` — no new harness needed.

## Status

- Saturn-bny re-attest: ✅ GREEN on the prongs it targeted.
- Saturn-ao6 stays closed; re-attestation lives here as a delta.
- Saturn-9ha tracks the residual mid-stream-edit drift.
