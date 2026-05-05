import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, inject_manual_endpoint, LOCAL_OLLAMA, DEFAULT_MODEL

OUT = results_dir("walkthrough_may05_eve")
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
    raise RuntimeError("saturn web failed to start")


def shot(page, name, full_page=True):
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    return str(path.relative_to(ROOT))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="walk-"))
    cfg = tmp / "admin_config.json"
    port = freeport()
    origin = f"http://127.0.0.1:{port}"
    proc = spawn(port, cfg)
    shots = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            page.add_init_script(
                "window.localStorage.setItem('chat-accepted', '1');"
                "window.localStorage.setItem('saturn-model-params', JSON.stringify({max_tokens: 4000}));"
            )

            page.goto(f"{origin}/login", wait_until="domcontentloaded")
            shots["01_admin_gate"] = shot(page, "01_admin_gate.png")

            page.fill("#pw", "Saturn")
            page.click("#submit")
            page.wait_for_function(
                "() => document.getElementById('change-form').style.display === 'block'",
                timeout=8_000,
            )
            shots["02_change_password"] = shot(page, "02_change_password.png")

            page.fill("#new1", "walkthrough-pw-9")
            page.fill("#new2", "walkthrough-pw-9")
            page.click("#change-submit")
            page.wait_for_url(f"{origin}/", timeout=8_000)

            page.wait_for_selector("nav.tabs", state="attached", timeout=8_000)
            page.wait_for_selector("#discover.page.active", timeout=4_000)
            shots["03_network_scan"] = shot(page, "03_network_scan.png")

            page.evaluate("() => document.querySelector('.tab[data-tab=\"system\"]').click()")
            page.wait_for_selector("#system.page.active", timeout=4_000)
            shots["04_system_integrate"] = shot(page, "04_system_integrate.png")

            page.evaluate("() => { window.location.hash = 'admin'; }")
            time.sleep(0.5)
            try:
                page.wait_for_function(
                    "() => { const p = document.getElementById('admin-configure-page');"
                    " return p && !p.classList.contains('hidden'); }",
                    timeout=4_000,
                )
            except Exception:
                pass
            admin_visible = page.evaluate(
                "() => { const p = document.getElementById('admin-configure-page');"
                " if (!p) return false;"
                " const cs = window.getComputedStyle(p);"
                " const r = p.getBoundingClientRect();"
                " return cs.display !== 'none' && cs.visibility !== 'hidden'"
                " && r.width > 0 && r.height > 0; }"
            )
            shots["05_system_admin_subview"] = shot(page, "05_system_admin_subview.png")

            page.evaluate("""() => {
              window.location.hash = '';
              const p = document.getElementById('admin-configure-page');
              if (p) { p.classList.add('hidden'); p.style.display = 'none'; }
            }""")
            time.sleep(0.3)

            page.evaluate(f"""(args) => {{
              const a = document.getElementById('ep-name'); if (a) a.value = args.name;
              const b = document.getElementById('ep-url'); if (b) b.value = args.url;
              const c = document.getElementById('ep-type'); if (c) c.value = args.api_type;
              const btn = document.getElementById('ep-add'); if (btn) btn.click();
            }}""", {"name": "local", "url": LOCAL_OLLAMA, "api_type": "openai"})
            time.sleep(0.4)

            page.evaluate("() => document.querySelector('.tab[data-tab=\"chat\"]').click()")
            try:
                page.wait_for_selector("#chat.page.active", timeout=4_000)
            except Exception:
                pass

            try:
                page.wait_for_function(
                    f"() => Array.from(document.getElementById('service-select').options)"
                    f".some(o => o.value === '__manual__:local')",
                    timeout=8_000,
                )
                page.select_option("#service-select", "__manual__:local")
            except Exception:
                pass

            time.sleep(0.5)
            btn = page.query_selector("#plus-menu-btn")
            if btn:
                try: btn.click(force=True)
                except Exception: pass
            time.sleep(0.5)
            menu_state = page.evaluate("""() => {
              const m=document.getElementById('plus-menu');
              return {hidden:m.classList.contains('hidden'),
                      rect:m.getBoundingClientRect()};
            }""")
            print("plus-menu state before shot:", menu_state)
            if menu_state["hidden"]:
                page.evaluate("""() => {
                  document.getElementById('plus-menu').classList.remove('hidden');
                }""")
                time.sleep(0.3)
            page.evaluate("""() => {
              const m = document.getElementById('plus-menu');
              if (!m) return;
              const area = m.closest('.chat-input-area');
              if (area) area.style.overflow = 'visible';
            }""")
            time.sleep(0.2)
            shots["06_chat_plus_menu"] = shot(page, "06_chat_plus_menu.png", full_page=False)

            page.evaluate("() => document.getElementById('plus-mcp').click()")
            try:
                page.wait_for_selector("#tools-close", state="visible", timeout=4_000)
            except Exception:
                pass
            time.sleep(0.4)
            shots["07_mcp_popup"] = shot(page, "07_mcp_popup.png")

            close_btn = page.query_selector("#tools-close")
            if close_btn:
                close_btn.click(); time.sleep(0.3)

            opened = page.evaluate("""() => {
              const btns = Array.from(document.querySelectorAll('.chat-settings-btn'));
              for (const b of btns) {
                const r = b.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) { b.click(); return true; }
              }
              if (btns.length) { btns[0].click(); return true; }
              return false;
            }""")
            try:
                page.wait_for_function(
                    "() => { const p = document.getElementById('chat-settings-popup');"
                    " return p && !p.classList.contains('hidden'); }",
                    timeout=4_000,
                )
            except Exception:
                pass
            time.sleep(0.3)
            param_count = page.evaluate(
                "() => document.querySelectorAll('#chat-settings-popup .param-row, "
                "#chat-settings-popup label.param, #chat-settings-popup [data-param]').length"
            )
            shots["08_settings_popup"] = shot(page, "08_settings_popup.png")

            ctx.close(); browser.close()

            out = {
                "shots": shots,
                "admin_subview_computed_visible": admin_visible,
                "settings_param_count": param_count,
            }
            (OUT / "result.json").write_text(json.dumps(out, indent=2))
            print(json.dumps(out, indent=2))
    finally:
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
