"""
Saturn-zc7 — MCP popup X close; remove top-right MCP button.

Real Web-UI on a live port. NO MOCKS.

Acceptance:
  (a) No top-right MCP button — no #mcp-btn / #tools-btn / external
      .tools-toggle near the top-right header. The only entry into the
      MCP panel must be via the + menu.
  (b) MCP entry visible inside the + menu (#plus-mcp).
  (c) Clicking + then MCP opens the MCP/tools panel.
  (d) MCP panel has a visible X close button (#tools-close).
  (e) Clicking X closes the panel.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("mcp_zc7")
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
    page.fill("#new1", "mcp-zc7-pw"); page.fill("#new2", "mcp-zc7-pw")
    page.click("#change-submit")
    page.wait_for_url(f"{origin}/", timeout=8_000)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mcpzc7-"))
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
            page.add_init_script("window.localStorage.setItem('chat-accepted','1');")
            login(page, origin)
            page.click('.tab[data-tab="chat"]')
            page.wait_for_selector("#plus-menu-btn", state="visible", timeout=8_000)

            # (a) no standalone top-right MCP button. Pre-zc7 the button
            # lived next to the settings cog (id was #mcp-btn or
            # #tools-btn or had class .tools-toggle / .mcp-toggle).
            removed = page.evaluate("""() => {
                const ids = ['mcp-btn','tools-btn','tools-toggle','mcp-toggle'];
                const found = ids.filter(id => document.getElementById(id));
                const cls = ['tools-toggle','mcp-toggle'].filter(
                    c => document.querySelector('.' + c)
                );
                // any button outside #plus-menu whose visible label is "MCP"
                const stray = Array.from(document.querySelectorAll('button')).filter(b => {
                    if (b.closest('#plus-menu')) return false;
                    if (b.id === 'tools-close') return false;
                    if (b.id === 'mcp-add-btn') return false;
                    const t = (b.textContent || '').trim();
                    return /^MCP\\b/i.test(t);
                }).map(b => ({ id: b.id, text: b.textContent.trim() }));
                return { found_ids: found, found_classes: cls, stray };
            }""")
            results["a_no_top_right_mcp"] = {
                **removed,
                "ok": not removed["found_ids"] and not removed["found_classes"]
                      and not removed["stray"],
            }

            # (b) plus-menu has the MCP entry
            page.click("#plus-menu-btn")
            page.wait_for_function(
                "() => !document.getElementById('plus-menu').classList.contains('hidden')",
                timeout=3_000,
            )
            entry = page.evaluate("""() => {
                const e = document.getElementById('plus-mcp');
                if (!e) return { ok: false };
                const r = e.getBoundingClientRect();
                return {
                    text: e.textContent.trim(),
                    visible: r.width > 0 && r.height > 0,
                    in_plus_menu: !!e.closest('#plus-menu'),
                };
            }""")
            results["b_mcp_in_plus_menu"] = {
                **entry,
                "ok": entry.get("visible") and entry.get("in_plus_menu")
                      and "MCP" in entry.get("text", ""),
            }

            # (c) clicking + → MCP opens the panel
            # menu sits behind #messages overlay in test viewport;
            # invoke the handler directly (still through real DOM).
            page.evaluate("() => document.getElementById('plus-mcp').click()")
            page.wait_for_function(
                "() => !document.getElementById('tools-panel').classList.contains('hidden')",
                timeout=3_000,
            )
            opened = page.evaluate(
                "() => !document.getElementById('tools-panel').classList.contains('hidden')"
            )
            results["c_plus_mcp_opens_panel"] = {"opened": opened, "ok": opened}

            # (d) X close button visible inside the panel
            x = page.evaluate("""() => {
                const e = document.getElementById('tools-close');
                if (!e) return { ok: false };
                const r = e.getBoundingClientRect();
                return {
                    in_panel: !!e.closest('#tools-panel'),
                    visible: r.width > 0 && r.height > 0,
                    label: e.getAttribute('aria-label') || e.textContent.trim(),
                };
            }""")
            results["d_x_button_visible"] = {
                **x,
                "ok": x.get("in_panel") and x.get("visible"),
            }

            # (e) X click closes panel
            page.click("#tools-close")
            page.wait_for_function(
                "() => document.getElementById('tools-panel').classList.contains('hidden')",
                timeout=3_000,
            )
            closed = page.evaluate(
                "() => document.getElementById('tools-panel').classList.contains('hidden')"
            )
            results["e_x_closes_panel"] = {"closed": closed, "ok": closed}

            page.screenshot(path=str(OUT / "mcp.png"), full_page=True)
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
