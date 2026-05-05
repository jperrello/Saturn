# CONTRACT — Saturn-9ha: mid-stream edit-save drift fix

**Status:** GREEN. Hardener landed strategy (b) at commit `dcf235b` on
`autonomous/promo-push`: the save handler aborts `activeController`
and waits up to 2s for `sending===false` before doing the
sibling-remove + `send()`.

## Spec restatement (falsifiable)

While an assistant message is streaming, opening the editor on the user
message and clicking Save & regenerate MUST leave the chat in a
consistent state once the dust settles:

1. `chat.messages.length` (localStorage `saturn-chats[0].messages`)
   equals `#messages .msg` count.
2. No uncaught JS errors.

These were the two failing predicates from prong D of
`tests/bombadil/edit_ao6.py`. The other four prongs (A/B/C/E) were
already green post-bny — re-verified here as a guard against
regression from the new abort/wait logic.

## Test file

`tests/bombadil/edit_ao6.py` (no changes — same harness re-run)

## Run command

```
SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/edit_ao6.py
```

Saturn web restarted from current HEAD with `dcf235b` in tree before
re-running.

## Captured GREEN run (verbatim summary)

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
      "final_dom": 2, "final_stored": 2,
      "dom_eq_stored": true,
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
    "D_midstream_no_drift": true,
    "E_attachment_inlined_on_edit": true
  },
  "js_errors": [],
  "pass": true
}
```

Full results: `.brutus/Saturn-9ha/result.json`.

## Per-prong delta vs. post-bny run

| Prong | Pre-9ha | Post-9ha | Notes |
|-------|---------|----------|-------|
| A | PASS | PASS | unchanged |
| B | PASS | PASS | unchanged |
| C | PASS | PASS | unchanged |
| D | **FAIL** (DOM=0, stored=1; stranded asst) | **PASS** (DOM=2, stored=2) | 9ha fix |
| E | PASS | PASS | unchanged |

Strategy (b) — abort the in-flight controller + wait for `sending=false`
before resending — was the right pick: the user's edit gets the new
stream they actually wanted, rather than the (a) "disable Save while
sending" alternative which would have just bounced the click silently.

## Bead

Saturn-9ha — closes on this attestation. Saturn-ao6 chain (cbt.2.d)
fully green: bny + 9ha together close the original flake.
