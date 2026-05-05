"""
Saturn-f3o — chat + button moved inside message bar; white-on-transparent.

Real Web-UI on a live port. NO MOCKS.

Acceptance:
  (a) #plus-menu-btn is a child of .chat-input-area (the message bar)
      — same parent as the textarea and send button.
  (b) Icon is visible against its background. Computed `color` of the
      button is white-ish (#fff), but the button's effective background
      is not white — proving "white on transparent" rather than the
      previous white-on-white invisible state.
  (c) Clicking + opens .plus-menu; menu is positioned above the bar
      (top of menu < top of bar in client coords).
  (d) Layout mirrors send button: + button and send button share the
      same parent (.chat-input-area); + sits to the left of the
      textarea, send sits to the right.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("plusbar_f3o")
ROOT = Path(__file__).resolve().parents[2]


def freeport():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def spawn(port, cfg_path):
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
                time.sleep(0.4); return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"saturn web did not start on {port}")


def login(page, origin):
    page.goto(f"{origin}/login", wait_until="domcontentloaded")
    page.fill("#pw", "Saturn"); page.click("#submit")
    page.wait_for_function(
        "() => document.getElementById('change-form').style.display === 'block'",
        timeout=8_000,
    )
    page.fill("#new1", "plusbar-f3o"); page.fill("#new2", "plusbar-f3o")
    page.click("#change-submit")
    page.wait_for_url(f"{origin}/", timeout=8_000)


def parse_rgb(s):
    s = s.strip()
    if not s.startswith("rgb"):
        return None
    inner = s[s.find("(")+1:s.rfind(")")]
    parts = [p.strip() for p in inner.split(",")]
    try:
        return [float(parts[0]), float(parts[1]), float(parts[2]),
                float(parts[3]) if len(parts) > 3 else 1.0]
    except Exception:
        return None


def main():
    tmp = Path(tempfile.mkdtemp(prefix="plusbarf3o-"))
    cfg = tmp / "admin_config.json"
    port = freeport()
    origin = f"http://127.0.0.1:{port}"
    proc = spawn(port, cfg)
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.add_init_script(
                "window.localStorage.setItem('chat-accepted', '1');"
            )
            login(page, origin)
            page.click('.tab[data-tab="chat"]')
            page.wait_for_selector("#plus-menu-btn", state="visible", timeout=8_000)

            # (a) parent of plus is .chat-input-area
            parent_info = page.evaluate("""() => {
                const b = document.getElementById('plus-menu-btn');
                if (!b) return { ok: false };
                const par = b.parentElement;
                return {
                    parent_class: par && par.className,
                    is_chat_input_area: par && par.classList.contains('chat-input-area'),
                };
            }""")
            results["a_parent_is_message_bar"] = {
                **parent_info,
                "ok": parent_info.get("is_chat_input_area") is True,
            }

            # (b) icon color white, container bg not white
            colors = page.evaluate("""() => {
                const b = document.getElementById('plus-menu-btn');
                const bg = document.querySelector('.chat-input-area');
                const cs = getComputedStyle(b);
                const bbg = getComputedStyle(bg);
                return {
                    btn_color: cs.color,
                    btn_bg: cs.backgroundColor,
                    bar_bg: bbg.backgroundColor,
                };
            }""")
            btn = parse_rgb(colors["btn_color"]) or [0,0,0,1]
            barbg = parse_rgb(colors["bar_bg"]) or [0,0,0,1]
            white_text = btn[0] > 240 and btn[1] > 240 and btn[2] > 240
            # not white-on-white: bar background must not also be near-white
            bar_not_white = not (barbg[0] > 240 and barbg[1] > 240 and barbg[2] > 240)
            results["b_white_on_non_white"] = {
                **colors, "btn_white": white_text, "bar_not_white": bar_not_white,
                "ok": white_text and bar_not_white,
            }

            # (c) click + opens menu, anchored above the bar
            page.click("#plus-menu-btn")
            page.wait_for_function(
                "() => !document.getElementById('plus-menu').classList.contains('hidden')",
                timeout=3_000,
            )
            geo = page.evaluate("""() => {
                const m = document.getElementById('plus-menu');
                const a = document.querySelector('.chat-input-area');
                const mr = m.getBoundingClientRect();
                const ar = a.getBoundingClientRect();
                return {
                    menu_top: mr.top, menu_bottom: mr.bottom,
                    bar_top: ar.top, bar_bottom: ar.bottom,
                };
            }""")
            results["c_menu_above_bar"] = {
                **geo,
                "ok": geo["menu_bottom"] <= geo["bar_top"] + 8
                      and geo["menu_top"] < geo["bar_top"],
            }

            # (d) plus and send share the same parent; plus left of textarea,
            # send right of textarea (mirror layout)
            layout = page.evaluate("""() => {
                const plus = document.getElementById('plus-menu-btn');
                const send = document.getElementById('send-btn');
                const ta = document.getElementById('chat-input');
                if (!plus || !send || !ta) return { ok: false };
                return {
                    same_parent: plus.parentElement === send.parentElement
                                  && send.parentElement === ta.parentElement,
                    plus_left_of_ta: plus.getBoundingClientRect().left
                                      < ta.getBoundingClientRect().left,
                    send_right_of_ta: send.getBoundingClientRect().right
                                       > ta.getBoundingClientRect().right,
                };
            }""")
            results["d_mirrors_send"] = {
                **layout,
                "ok": layout.get("same_parent") and layout.get("plus_left_of_ta")
                      and layout.get("send_right_of_ta"),
            }

            # (e) Saturn-bpj guard — menu must be ACTUALLY visible on screen,
            # not merely have .open/!hidden class and a non-zero rect. Detects
            # the .chat-input-area overflow:hidden class of bug where the menu
            # lays out above the bar but is clipped to invisible pixels.
            vis = page.evaluate("""() => {
                const m = document.getElementById('plus-menu');
                if (!m) return { ok: false, reason: 'no-menu' };
                const cs = getComputedStyle(m);
                const r = m.getBoundingClientRect();
                if (cs.display === 'none' || cs.visibility === 'hidden'
                    || parseFloat(cs.opacity) < 0.01)
                    return { ok: false, reason: 'computed-hidden',
                             display: cs.display, visibility: cs.visibility,
                             opacity: cs.opacity };
                if (r.width <= 0 || r.height <= 0)
                    return { ok: false, reason: 'zero-rect', rect: r };
                // walk ancestors: if any ancestor with overflow:hidden|clip
                // has a client rect that does NOT contain the menu rect, the
                // menu is visually clipped.
                let p = m.parentElement;
                while (p && p !== document.body) {
                    const pcs = getComputedStyle(p);
                    if (pcs.overflow === 'hidden' || pcs.overflowX === 'hidden'
                        || pcs.overflowY === 'hidden' || pcs.overflow === 'clip') {
                        const pr = p.getBoundingClientRect();
                        if (r.top < pr.top || r.bottom > pr.bottom
                            || r.left < pr.left || r.right > pr.right) {
                            return { ok: false, reason: 'clipped-by-ancestor',
                                     ancestor: p.className || p.id,
                                     menu_rect: r, ancestor_rect: pr };
                        }
                    }
                    p = p.parentElement;
                }
                // hit-test the menu center — must hit the menu or a descendant.
                const cx = r.left + r.width / 2;
                const cy = r.top + r.height / 2;
                const hit = document.elementFromPoint(cx, cy);
                const hits_menu = hit && (hit === m || m.contains(hit));
                return { ok: !!hits_menu, reason: hits_menu ? 'visible' : 'hit-test-miss',
                         hit_tag: hit && hit.tagName, hit_id: hit && hit.id,
                         hit_class: hit && hit.className,
                         menu_center: { x: cx, y: cy } };
            }""")
            results["e_menu_actually_visible"] = vis

            page.screenshot(path=str(OUT / "plusbar.png"), full_page=True)
            ctx.close()

            oracle = {k: v["ok"] for k, v in results.items()}
            out = {"results": results, "oracle": oracle, "pass": all(oracle.values())}
            finalize(out, browser, OUT)
    finally:
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
