"""
Saturn-ao6 (cbt.2.d) — edit-and-regenerate flake hunt.

Per athena: regenerate is client-side history mutation + resend at
Web-UI/app.js:1991, save-edit at Web-UI/app.js:4258. UI-only test for
five behaviors:

  A. Rapid edit clicks idempotent (5 clicks → 1 textarea).
  B. Edit → cancel → re-edit cleanly round-trips.
  C. Edit → save & regenerate happy path: chat.messages.length ===
     DOM `.msg` count, last user message text matches edit.
  D. Mid-stream edit attempt: after the dust settles, DOM === storage.
  E. Edit with attachment present: regenerated user message contains
     `--- File: <name>` marker AND the edited text.

UI-only. Live Web-UI on $SATURN_PORT, live Ollama via __manual__:local.
No mocks.
"""

import time, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import (
    setup_chat_page, send_message, chat_state, results_dir, finalize,
)

OUT = results_dir("edit_ao6")
HOVER_USER = ("() => document.querySelector('.msg.user') && "
              "document.querySelector('.msg.user').dispatchEvent("
              "new MouseEvent('mouseover',{bubbles:true}))")
CLICK_EDIT = "() => document.querySelector('.msg.user .edit-btn')?.click()"


def wait_stream_done(page, timeout_s=60):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not page.evaluate("() => !!document.querySelector('.msg.assistant .cursor')"):
            break
        time.sleep(0.2)
    time.sleep(0.5)


def reset_page(page):
    page.evaluate("() => { try { localStorage.removeItem('saturn-chats'); } catch{} location.reload(); }")
    page.wait_for_load_state('domcontentloaded')
    setup_chat_page(page)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="edit-ao6-"))
    note = tmp / "note.txt"; note.write_text("CONTEXT: the answer is 42\n")

    results = {}
    js_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.on("pageerror", lambda exc: js_errors.append(str(exc)))
        setup_chat_page(page)

        # --- A. rapid-edit guard ---
        send_message(page, "say one word: hi")
        page.evaluate(HOVER_USER)
        for _ in range(5):
            page.evaluate(CLICK_EDIT)
        results["A_rapid_clicks_one_textarea"] = page.evaluate(
            "() => document.querySelectorAll('.msg.user .edit-textarea').length"
        ) == 1

        # --- B. cancel + re-edit ---
        page.click('.msg.user .edit-cancel'); page.wait_for_timeout(100)
        bubble_back = page.evaluate(
            "() => !!document.querySelector('.msg.user .bubble') && "
            "!document.querySelector('.msg.user .edit-textarea')"
        )
        page.evaluate(HOVER_USER); page.evaluate(CLICK_EDIT)
        re_open = page.evaluate(
            "() => document.querySelectorAll('.msg.user .edit-textarea').length === 1"
        )
        page.click('.msg.user .edit-cancel')
        results["B_cancel_then_reedit"] = bubble_back and re_open

        # --- C. edit-save happy path ---
        before = chat_state(page)
        page.evaluate(HOVER_USER); page.evaluate(CLICK_EDIT)
        page.fill('.msg.user .edit-textarea', "say one word: bye")
        page.click('.msg.user .edit-save')
        try: page.wait_for_selector('.msg.assistant .cursor', timeout=10_000)
        except Exception: pass
        wait_stream_done(page)
        after = chat_state(page)
        results["C_edit_save_happy"] = {
            "before_dom": before["dom"], "before_stored": before["stored"],
            "after_dom": after["dom"], "after_stored": after["stored"],
            "last_user_matches_edit": "bye" in after["lastUser"],
            "dom_eq_stored": after["dom"] == after["stored"],
            "no_js_errors": len(js_errors) == 0,
        }

        # --- D. mid-stream edit-save flake ---
        reset_page(page)
        send_message(page,
            "Write a 2000-word story about a dragon. Be detailed and verbose.",
            wait_complete=False,
        )
        time.sleep(2.0)
        streaming_now = page.evaluate(
            "() => !!document.querySelector('.msg.assistant .cursor')"
        )
        edit_attempted = edit_saved = False
        try:
            page.evaluate(HOVER_USER); page.evaluate(CLICK_EDIT)
            ta_present = page.evaluate(
                "() => !!document.querySelector('.msg.user .edit-textarea')"
            )
            edit_attempted = ta_present
            if ta_present:
                page.fill('.msg.user .edit-textarea', "say one word: cat")
                page.click('.msg.user .edit-save')
                edit_saved = True
        except Exception:
            pass
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            cur = page.evaluate("() => !!document.querySelector('.msg.assistant .cursor')")
            disabled = page.evaluate("() => document.getElementById('send-btn').disabled")
            text = page.evaluate("() => document.getElementById('send-btn').textContent")
            if not cur and not disabled and text.strip().lower() != "stop":
                break
            time.sleep(0.3)
        time.sleep(0.5)
        d = chat_state(page)
        results["D_midstream_edit"] = {
            "streaming_when_edit_clicked": streaming_now,
            "edit_textarea_opened": edit_attempted,
            "save_invoked": edit_saved,
            "final_dom": d["dom"], "final_stored": d["stored"],
            "dom_eq_stored": d["dom"] == d["stored"],
            "no_js_errors": len(js_errors) == 0,
        }

        # --- E. edit with attachment present ---
        reset_page(page)
        send_message(page, "say one word: ok")
        page.set_input_files('#file-input', str(note)); page.wait_for_timeout(150)
        badge = page.evaluate(
            "() => { const b=document.getElementById('file-badge'); "
            "return !!b && !b.classList.contains('hidden'); }"
        )
        page.evaluate(HOVER_USER); page.evaluate(CLICK_EDIT)
        page.fill('.msg.user .edit-textarea', "summarize this file")
        page.click('.msg.user .edit-save')
        try: page.wait_for_selector('.msg.assistant .cursor', timeout=10_000)
        except Exception: pass
        wait_stream_done(page)
        e = chat_state(page)
        results["E_edit_with_attachment"] = {
            "badge_was_visible": badge,
            "stored_user_has_file_marker": "--- File: note.txt" in e["lastUser"],
            "stored_user_has_edit_text": "summarize this file" in e["lastUser"],
            "dom_eq_stored": e["dom"] == e["stored"],
            "no_js_errors": len(js_errors) == 0,
        }

        page.screenshot(path=str(OUT / "final.png"), full_page=True)

    oracle = {
        "A_rapid_clicks_idempotent": results["A_rapid_clicks_one_textarea"],
        "B_cancel_reedit_clean": results["B_cancel_then_reedit"],
        "C_edit_save_consistent": (
            results["C_edit_save_happy"]["dom_eq_stored"]
            and results["C_edit_save_happy"]["last_user_matches_edit"]
            and results["C_edit_save_happy"]["after_dom"] >= results["C_edit_save_happy"]["before_dom"]
            and results["C_edit_save_happy"]["no_js_errors"]
        ),
        "D_midstream_no_drift": (
            results["D_midstream_edit"]["dom_eq_stored"]
            and results["D_midstream_edit"]["no_js_errors"]
        ),
        "E_attachment_inlined_on_edit": (
            results["E_edit_with_attachment"]["badge_was_visible"]
            and results["E_edit_with_attachment"]["stored_user_has_file_marker"]
            and results["E_edit_with_attachment"]["stored_user_has_edit_text"]
            and results["E_edit_with_attachment"]["dom_eq_stored"]
            and results["E_edit_with_attachment"]["no_js_errors"]
        ),
    }
    out = {"results": results, "oracle": oracle, "js_errors": js_errors,
           "pass": all(oracle.values())}
    finalize(out, browser, OUT)


if __name__ == "__main__":
    main()
