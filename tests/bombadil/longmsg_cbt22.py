"""
Saturn-cbt.2.2 — attachment composer UX contract.

Six contracts probed against the live Web-UI. No mocks. Fixture files are
generated in a tempdir at run time and fed via Playwright set_input_files.

  C1. + menu opens an attachment picker, file selection accepted.
  C2. supported types render preview/badge in the composer BEFORE send.
  C3. unsupported type → inline error visible, send is no-op or blocked.
  C4. oversize file (> configured max) → inline error w/ size context,
      send blocked.
  C5. attachment + text combined → both arrive in the conversation.
  C6. attachment-only behavior matches whatever hardener documents
      (reject, or send-with-empty-text).

Selectors / limits / messages are pulled from constants below; reconcile
with hardener's commit before running. TODOs flag what to confirm.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import (
    gate_init_script, inject_manual_endpoint, open_chat_with_endpoint,
    attach_console_error_collector, results_dir,
)

OUT = results_dir("longmsg_cbt22")
ROOT = Path(__file__).resolve().parents[2]
GATE_PW_NEW = "cbt22-verify-pw-9"

# Reconciled with 4a92f83 (Web-UI/app.js).
SEL_PLUS_BTN = "#plus-menu-btn"     # opens the + menu
SEL_PLUS_ATTACH = "#plus-attach"    # menu item that triggers the file input
SEL_FILE_INPUT = "#file-input"
SEL_BADGE = "#file-badge"           # visible (no .hidden) when previewed
SEL_BADGE_NAME = "#file-badge-name"
SEL_BADGE_THUMB = "#file-badge-thumb"
SEL_BADGE_ICON = "#file-badge-icon"
SEL_BADGE_REMOVE = "#file-badge-remove"
SEL_INLINE_ERROR = "#file-error"    # visible (no .hidden) when error
SEL_SEND_BTN = "#send-btn"

MAX_BYTES = 5 * 1024 * 1024
OVERSIZE_BYTES = 6 * 1024 * 1024  # just over the 5MB cap

SUPPORTED_TYPES = ("text", "image", "pdf")


def _freeport():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def _spawn(port, cfg_path):
    env = dict(os.environ)
    env["SATURN_ADMIN_CONFIG_PATH"] = str(cfg_path)
    env["SATURN_ADMIN_PASSWORD"] = "x" * 16
    env["SATURN_ADMIN_TOKEN"] = "y" * 32
    env["SATURN_RUNNER_TOKEN"] = "z" * 32
    proc = subprocess.Popen(
        [sys.executable, "-m", "saturn", "web", "--port", str(port)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                time.sleep(0.4)
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"saturn web did not start on {port}")


def _login(page, origin):
    status = page.request.get(f"{origin}/api/auth/status").json()
    must_change = bool(status.get("must_change"))
    pw = "Saturn" if must_change else GATE_PW_NEW
    page.goto(f"{origin}/login", wait_until="domcontentloaded")
    page.fill("#pw", pw)
    page.click("#submit")
    if must_change:
        page.wait_for_function(
            "() => document.getElementById('change-form').style.display === 'block'",
            timeout=8_000,
        )
        page.fill("#new1", GATE_PW_NEW)
        page.fill("#new2", GATE_PW_NEW)
        page.click("#change-submit")
    page.wait_for_url(f"{origin}/", timeout=10_000)


def _setup(page, origin):
    page.add_init_script(gate_init_script({}))
    _login(page, origin)
    page.goto(origin, wait_until="domcontentloaded")
    inject_manual_endpoint(page)
    open_chat_with_endpoint(page)


def _fixtures(tmp):
    txt = tmp / "hello.txt"
    txt.write_text("hello attachment\n")

    # 1x1 PNG
    png = tmp / "pixel.png"
    png.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    ))

    # ~50KB minimal PDF
    pdf = tmp / "doc.pdf"
    body = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\n"
    )
    body += b"% pad " + (b"x" * 50_000) + b"\n"
    body += b"xref\n0 4\n0000000000 65535 f\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
    pdf.write_bytes(body)

    # unsupported: .exe with MZ header
    bad = tmp / "evil.exe"
    bad.write_bytes(b"MZ" + b"\x00" * 1024)

    # oversize: just over MAX_BYTES, with a SUPPORTED ext so the size
    # check is what triggers (ext check fires first in attachFile()).
    big = tmp / "huge.txt"
    with open(big, "wb") as f:
        f.seek(OVERSIZE_BYTES - 1)
        f.write(b"\0")

    return {"txt": txt, "png": png, "pdf": pdf, "bad": bad, "big": big}


def _open_picker(page):
    page.click(SEL_PLUS_BTN)
    # menu must show before #plus-attach is clickable
    page.wait_for_function(
        "() => { const m = document.getElementById('plus-menu');"
        " return m && !m.classList.contains('hidden'); }",
        timeout=3_000,
    )


def _attach(page, path):
    # We don't actually need to click #plus-attach to wire set_input_files;
    # the input exists in the DOM and Playwright drives it directly. Open
    # the menu first to mimic real flow + ensure no listener interferes.
    _open_picker(page)
    page.set_input_files(SEL_FILE_INPUT, str(path))


def _badge_visible(page):
    return page.evaluate(
        "(s) => { const el = document.querySelector(s);"
        " return !!(el && !el.classList.contains('hidden')); }",
        SEL_BADGE,
    )


def _error_text(page):
    return page.evaluate(
        "(s) => { const el = document.querySelector(s);"
        " if (!el || el.classList.contains('hidden')) return '';"
        " return (el.textContent || '').trim(); }",
        SEL_INLINE_ERROR,
    )


def _wait_no_error(page, timeout_ms=2_000):
    # Used between c2 sub-cases: when the previous attachment was cleared,
    # re-attaching another file from a different fixture should clear any
    # transient error state.
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if not _error_text(page):
            return True
        time.sleep(0.05)
    return False


def _clear_attachment(page):
    # Click the badge remove button if visible; otherwise reset input value
    # directly so the next set_input_files dispatches a 'change' event.
    page.evaluate(
        "() => { const b = document.getElementById('file-badge-remove');"
        " if (b) b.click(); }"
    )
    time.sleep(0.1)


def c1_picker_opens(p, origin, fx):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    try:
        _attach(page, fx["txt"])
        # picker accepted at least one file (preview node OR input has files)
        accepted = page.evaluate(
            "(s) => { const el = document.querySelector(s);"
            " return !!(el && el.files && el.files.length > 0); }",
            SEL_FILE_INPUT,
        )
        page.screenshot(path=str(OUT / "c1_after.png"), full_page=False)
        return {"accepted": accepted, "pass": accepted}
    finally:
        browser.close()


def c2_supported_preview(p, origin, fx):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    try:
        per = {}
        for kind, key in (("text", "txt"), ("image", "png"), ("pdf", "pdf")):
            _attach(page, fx[key])
            try:
                # PDF round-trips through the server (pypdf), so allow longer.
                deadline = time.monotonic() + (10 if kind == "pdf" else 4)
                shown = False
                while time.monotonic() < deadline:
                    if _badge_visible(page):
                        shown = True
                        break
                    time.sleep(0.1)
                # also confirm the badge name matches our fixture
                name = page.evaluate(
                    "() => (document.getElementById('file-badge-name')"
                    " || {}).textContent || ''"
                )
                per[kind] = shown and fx[key].name in name
            except Exception:
                per[kind] = False
            _clear_attachment(page)
            _wait_no_error(page)
        page.screenshot(path=str(OUT / "c2_after.png"), full_page=False)
        return {"per_type": per, "pass": all(per.get(k) for k in SUPPORTED_TYPES)}
    finally:
        browser.close()


def c3_unsupported_blocked(p, origin, fx):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    try:
        _attach(page, fx["bad"])
        # error appears
        try:
            page.wait_for_selector(SEL_INLINE_ERROR, timeout=4_000)
            err = _error_text(page)
        except Exception:
            err = ""
        # send must be blocked: either disabled, or click does not enqueue
        before_msgs = page.evaluate(
            "() => document.querySelectorAll('.msg.user').length"
        )
        try:
            page.click(SEL_SEND_BTN, timeout=1_500)
        except Exception:
            pass
        time.sleep(0.6)
        after_msgs = page.evaluate(
            "() => document.querySelectorAll('.msg.user').length"
        )
        page.screenshot(path=str(OUT / "c3_after.png"), full_page=False)
        return {
            "error_text": err,
            "messages_added": after_msgs - before_msgs,
            "pass": bool(err) and (after_msgs - before_msgs) == 0,
        }
    finally:
        browser.close()


def c4_oversize_blocked(p, origin, fx):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    try:
        _attach(page, fx["big"])
        try:
            page.wait_for_selector(SEL_INLINE_ERROR, timeout=6_000)
            err = _error_text(page)
        except Exception:
            err = ""
        before_msgs = page.evaluate(
            "() => document.querySelectorAll('.msg.user').length"
        )
        try:
            page.click(SEL_SEND_BTN, timeout=1_500)
        except Exception:
            pass
        time.sleep(0.6)
        after_msgs = page.evaluate(
            "() => document.querySelectorAll('.msg.user').length"
        )
        page.screenshot(path=str(OUT / "c4_after.png"), full_page=False)
        size_mentioned = any(
            tok in err.lower() for tok in ("mb", "size", "large", "limit")
        )
        return {
            "error_text": err,
            "size_context_mentioned": size_mentioned,
            "messages_added": after_msgs - before_msgs,
            "pass": bool(err) and size_mentioned and (after_msgs - before_msgs) == 0,
        }
    finally:
        browser.close()


def c5_attachment_plus_text(p, origin, fx):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errs = []
    attach_console_error_collector(page, errs)
    _setup(page, origin)
    try:
        # Per app.js:2069 displayText for text+image is just the user text;
        # the image rides on the wire as an OpenAI multimodal content array
        # (text part + image_url part). We verify both arrive by capturing
        # the outgoing /v1/chat/completions request body.
        captured = {"body": None}
        def on_request(req):
            if "/api/proxy/chat" in req.url and req.method == "POST":
                try:
                    captured["body"] = req.post_data
                except Exception:
                    pass
        page.on("request", on_request)

        _attach(page, fx["png"])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not _badge_visible(page):
            time.sleep(0.1)
        page.fill("#chat-input", "caption")
        page.click(SEL_SEND_BTN)
        page.wait_for_selector(".msg.user", timeout=10_000)
        bubble = page.evaluate(
            "() => { const ns = document.querySelectorAll('.msg.user .bubble');"
            " const u = ns[ns.length - 1];"
            " return u ? (u.textContent || '') : ''; }"
        )
        # Wait briefly for the chat completion request to fire.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not captured["body"]:
            time.sleep(0.1)
        body = captured["body"] or ""
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        last = (payload.get("messages") or [])[-1] if payload else {}
        content = last.get("content") if isinstance(last, dict) else None
        has_image_url = False
        has_text_part = False
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "image_url":
                        has_image_url = True
                    if part.get("type") == "text" and "caption" in (part.get("text") or ""):
                        has_text_part = True
        page.screenshot(path=str(OUT / "c5_after.png"), full_page=False)
        return {
            "bubble_text": bubble,
            "wire_has_image_url": has_image_url,
            "wire_has_text_caption": has_text_part,
            "console_errors": errs,
            "pass": ("caption" in bubble) and has_image_url and has_text_part,
        }
    finally:
        browser.close()


def c6_attachment_only(p, origin, fx):
    # Hardener decision: image-only send ALLOWED; bubble shows `[image: name]`
    # (displayText fallback in app.js when text is empty). User contract:
    # "message contains 'Attached image: <name>'" — that string is the wire
    # text; the bubble shows `[image: name]`. Verify the bubble pattern (DOM-
    # observable proof the send went through with an image marker).
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    try:
        _attach(page, fx["png"])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not _badge_visible(page):
            time.sleep(0.1)
        page.fill("#chat-input", "")
        before_msgs = page.evaluate(
            "() => document.querySelectorAll('.msg.user').length"
        )
        try:
            page.click(SEL_SEND_BTN, timeout=2_000)
        except Exception:
            pass
        page.wait_for_function(
            "(n) => document.querySelectorAll('.msg.user').length > n",
            arg=before_msgs, timeout=10_000,
        )
        bubble = page.evaluate(
            "() => { const ns = document.querySelectorAll('.msg.user .bubble');"
            " const u = ns[ns.length - 1];"
            " return u ? (u.textContent || '') : ''; }"
        )
        page.screenshot(path=str(OUT / "c6_after.png"), full_page=False)
        # Accept either the wire-text form or the displayText form.
        marker = (
            f"Attached image: {fx['png'].name}" in bubble
            or (f"[image: {fx['png'].name}]" in bubble)
        )
        return {
            "bubble_text": bubble,
            "marker_present": marker,
            "pass": marker,
        }
    finally:
        browser.close()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cbt22-"))
    cfg = tmp / "admin.json"
    fxdir = tmp / "fx"
    fxdir.mkdir()
    fx = _fixtures(fxdir)
    port = _freeport()
    origin = f"http://localhost:{port}"
    proc = _spawn(port, cfg)
    out = {}
    try:
        with sync_playwright() as p:
            for key, fn in [
                ("c1_picker_opens", c1_picker_opens),
                ("c2_supported_preview", c2_supported_preview),
                ("c3_unsupported_blocked", c3_unsupported_blocked),
                ("c4_oversize_blocked", c4_oversize_blocked),
                ("c5_attachment_plus_text", c5_attachment_plus_text),
                ("c6_attachment_only", c6_attachment_only),
            ]:
                try:
                    out[key] = fn(p, origin, fx)
                except Exception as e:
                    out[key] = {"pass": False, "error": f"{type(e).__name__}: {e}"}
        out["pass"] = all(v.get("pass") for v in out.values() if isinstance(v, dict))
        (OUT / "result.json").write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        sys.exit(0 if out["pass"] else 1)
    finally:
        try: proc.terminate()
        except Exception: pass
        try: proc.wait(timeout=5)
        except Exception: pass


if __name__ == "__main__":
    main()
