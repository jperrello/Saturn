"""
Saturn-6g1 (cbt.2.b) — attachments via + menu.

UI-only contract per athena: brutus has no server surface to gate the
attachment ingest path; the allowlist + size cap live entirely in
Web-UI/app.js:2409-2447 (FileReader.readAsText). Verifies all four
behaviors of `attachFile()`:

  1. Allowed extension under 100KB → file badge becomes visible, name shown.
  2. Disallowed extension → toast surfaces, NO badge appears.
  3. Allowed extension over 100KB → toast surfaces, NO badge appears.
  4. Plus-menu attach button routes to the same hidden file input.
  5. Badge remove (✕) clears the attachment + hides the badge.

ALLOWED_EXTS = .txt .md .py .js .ts .json .toml .yaml .yml .csv
MAX_FILE_SIZE = 100 * 1024 (102400 bytes)
"""

import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import (
    ORIGIN, gate_init_script, toast_text as _toast, reset_toast as _reset_toast,
    results_dir, finalize,
)

OUT = results_dir("attach_6g1")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="attach6g1-"))
    ok_txt = tmp / "hello.txt";  ok_txt.write_text("hello world\n")
    ok_md  = tmp / "notes.md";   ok_md.write_text("# heading\n")
    bad_ext = tmp / "rogue.exe"; bad_ext.write_text("MZ binary not really\n")
    too_big = tmp / "huge.txt";  too_big.write_text("x" * (200 * 1024))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.add_init_script(gate_init_script())

        page.goto(ORIGIN, wait_until="domcontentloaded")
        page.click('.tab[data-tab="chat"]')
        page.wait_for_selector("#file-input", state="attached", timeout=10_000)

        toast_text = lambda: _toast(page)
        reset_toast = lambda: _reset_toast(page)

        def badge_visible():
            return page.evaluate(
                "() => { const b=document.getElementById('file-badge'); "
                "return !!b && !b.classList.contains('hidden'); }"
            )

        def badge_name():
            return page.evaluate(
                "() => { const n=document.getElementById('file-badge-name'); "
                "return n ? n.textContent : ''; }"
            )

        def attach(path):
            page.set_input_files("#file-input", str(path))
            page.wait_for_timeout(150)

        results = {}

        # 1. allowed .txt
        attach(ok_txt)
        results["allowed_txt"] = {
            "badge_visible": badge_visible(),
            "badge_name_includes_filename": "hello.txt" in badge_name(),
            "no_toast": toast_text() == "",
        }

        # 5. badge remove clears
        page.click("#file-badge-remove")
        page.wait_for_timeout(100)
        results["badge_remove_clears"] = {
            "badge_hidden": not badge_visible(),
            "input_cleared": page.evaluate(
                "() => document.getElementById('file-input').value === ''"
            ),
        }

        # 2. disallowed extension
        reset_toast()
        attach(bad_ext)
        results["disallowed_ext"] = {
            "no_badge": not badge_visible(),
            "toast_unsupported": "Unsupported file type" in toast_text(),
        }

        # 3. oversize allowed extension
        reset_toast()
        attach(too_big)
        results["oversize"] = {
            "no_badge": not badge_visible(),
            "toast_too_large": "too large" in toast_text(),
        }

        # 4. plus-menu attach button shares the same input wiring.
        # Click + menu, then click "Attach". The file input is hidden so we
        # can't observe a native file picker in headless; instead verify
        # that #plus-attach exists, opens/closes the menu, and that the
        # subsequent set_input_files (i.e. simulated picker) lands the file
        # via the same attachFile() path.
        reset_toast()
        page.click("#plus-menu-btn")
        results["plus_menu_opens"] = page.evaluate(
            "() => !document.getElementById('plus-menu').classList.contains('hidden')"
        )
        # plus-attach handler hides the menu and clicks #file-input. We
        # short-circuit the picker by setting files directly afterward.
        page.evaluate(
            "() => document.getElementById('plus-attach').click()"
        )
        results["plus_attach_hides_menu"] = page.evaluate(
            "() => document.getElementById('plus-menu').classList.contains('hidden')"
        )
        attach(ok_md)
        results["plus_menu_attach_path"] = {
            "badge_visible": badge_visible(),
            "badge_name_includes_filename": "notes.md" in badge_name(),
        }

        # 6. exact-size boundary: file at exactly 100KB should be ACCEPTED
        # (size > MAX is the rejection condition; equal passes).
        page.click("#file-badge-remove"); page.wait_for_timeout(100)
        edge = tmp / "edge.txt"; edge.write_text("y" * (100 * 1024))
        reset_toast()
        attach(edge)
        results["exact_100kb_accepted"] = {
            "badge_visible": badge_visible(),
            "no_toast": toast_text() == "",
        }

        # 7. one-byte-over: 100KB + 1 should be REJECTED
        page.click("#file-badge-remove"); page.wait_for_timeout(100)
        over1 = tmp / "over1.txt"; over1.write_text("z" * (100 * 1024 + 1))
        reset_toast()
        attach(over1)
        results["one_byte_over_rejected"] = {
            "no_badge": not badge_visible(),
            "toast_too_large": "too large" in toast_text(),
        }

        page.screenshot(path=str(OUT / "final.png"), full_page=True)

        oracle = {
            "allowed_txt_attached": all(results["allowed_txt"].values()),
            "remove_clears": all(results["badge_remove_clears"].values()),
            "disallowed_rejected": all(results["disallowed_ext"].values()),
            "oversize_rejected": all(results["oversize"].values()),
            "plus_menu_works": (
                results["plus_menu_opens"]
                and results["plus_attach_hides_menu"]
                and all(results["plus_menu_attach_path"].values())
            ),
            "boundary_100kb_accepted": all(results["exact_100kb_accepted"].values()),
            "boundary_over_rejected": all(results["one_byte_over_rejected"].values()),
        }

        out = {"results": results, "oracle": oracle, "pass": all(oracle.values())}
        finalize(out, browser, OUT)


if __name__ == "__main__":
    main()
