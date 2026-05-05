"""
Saturn-k28 — Web-UI nav collapse to Network Scan / System / Chat.

Real Web-UI on a live port. NO MOCKS. Spawns its own `saturn web` so
we can authenticate cleanly through the gate (Saturn-828) and exercise
the page layout from a known state.

Verifies:
  (a) nav.tabs renders exactly 3 visible buttons.
  (b) No 'Admin Configure' top-level tab exists. No data-tab="admin".
  (c) Network Scan (#discover) shows no inline admin password input —
      no <input type="password"> inside #discover.
  (d) #admin-configure-page DOM is present (so admin-section is still
      reachable). With System active, triggering the documented entry
      point (`window.location.hash = 'admin'`) reveals the page and
      its admin-section fieldsets are populated.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("pages_k28")
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
    page.fill("#pw", "Saturn")
    page.click("#submit")
    # first run triggers change-form; set a real pw and land on /
    page.wait_for_function(
        "() => document.getElementById('change-form').style.display === 'block'",
        timeout=8_000,
    )
    page.fill("#new1", "k28-newpass-9")
    page.fill("#new2", "k28-newpass-9")
    page.click("#change-submit")
    page.wait_for_url(f"{origin}/", timeout=8_000)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pagesk28-"))
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
            login(page, origin)
            page.wait_for_selector("nav.tabs", state="attached", timeout=8_000)

            # (a) exactly 3 visible nav tabs
            nav = page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('nav.tabs button.tab'));
                return btns.map(b => ({
                    label: b.textContent.trim(),
                    tab: b.getAttribute('data-tab'),
                    visible: !!(b.offsetWidth || b.offsetHeight || b.getClientRects().length),
                }));
            }""")
            visible = [t for t in nav if t["visible"]]
            results["a_three_nav_buttons"] = {
                "tabs": nav, "visible_count": len(visible),
                "ok": len(visible) == 3 and {t["tab"] for t in visible} ==
                      {"discover", "system", "chat"},
            }

            # (b) no Admin Configure tab
            admin_tab = page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('nav.tabs button.tab'));
                return btns.some(b =>
                    b.getAttribute('data-tab') === 'admin' ||
                    /admin\\s*configure/i.test(b.textContent || '')
                );
            }""")
            results["b_no_admin_configure_tab"] = {
                "found": admin_tab, "ok": admin_tab is False,
            }

            # (c) Network Scan has no inline admin password input
            page.click('.tab[data-tab="discover"]')
            page.wait_for_selector("#discover.page.active", timeout=4_000)
            pw_inputs = page.evaluate("""() => {
                const root = document.getElementById('discover');
                if (!root) return -1;
                return root.querySelectorAll('input[type="password"]').length;
            }""")
            results["c_no_inline_admin_pw"] = {
                "password_inputs_in_discover": pw_inputs, "ok": pw_inputs == 0,
            }

            # (d) admin-section reachable inside System.
            page.click('.tab[data-tab="system"]')
            page.wait_for_selector("#system.page.active", timeout=4_000)
            on_system = page.evaluate(
                "() => document.getElementById('system').classList.contains('active')"
            )
            page.evaluate("() => { window.location.hash = 'admin'; }")
            try:
                page.wait_for_function(
                    "() => { const p = document.getElementById('admin-configure-page');"
                    " return p && !p.classList.contains('hidden'); }",
                    timeout=4_000,
                )
            except Exception:
                pass
            # Saturn-7mo guard: computed-style visible + no ancestor with
            # display:none up to <body>. .hidden absence is not enough.
            visibility = page.evaluate("""() => {
                const p = document.getElementById('admin-configure-page');
                if (!p) return { ok: false, reason: 'no-element' };
                const cs = getComputedStyle(p);
                const r = p.getBoundingClientRect();
                if (cs.display === 'none' || cs.visibility === 'hidden')
                    return { ok: false, reason: 'self-hidden',
                             display: cs.display, visibility: cs.visibility };
                if (r.width <= 0 || r.height <= 0)
                    return { ok: false, reason: 'zero-rect', rect: r };
                let q = p.parentElement;
                while (q && q !== document.body) {
                    const qc = getComputedStyle(q);
                    if (qc.display === 'none' || qc.visibility === 'hidden')
                        return { ok: false, reason: 'ancestor-hidden',
                                 ancestor: q.id || q.className,
                                 display: qc.display, visibility: qc.visibility };
                    q = q.parentElement;
                }
                return { ok: true, rect: r };
            }""")
            section_count = page.evaluate(
                "() => document.querySelectorAll("
                "'#admin-configure-page fieldset.admin-section').length"
            )
            results["d_admin_section_in_system"] = {
                "system_active": on_system,
                "admin_visibility": visibility,
                "admin_section_fieldsets": section_count,
                "ok": on_system and visibility.get("ok") is True
                      and section_count >= 8,
            }

            page.screenshot(path=str(OUT / "system_admin.png"), full_page=True)
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
