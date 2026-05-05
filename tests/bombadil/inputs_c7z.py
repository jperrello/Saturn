"""
Saturn-c7z — number-spinners removed, (i) info bubbles, numeric save.

Real Web-UI on a live port. NO MOCKS.

Acceptance:
  (a) No <input type="number"> in the DOM (spinner arrows can't render
      without it). At least one type=text + inputmode=decimal numeric.
  (b) Each numeric input is type=text and inputmode=decimal.
  (c) Clicking the (i) bubble next to a [data-info] label spawns
      .info-pop containing the data-info text.
  (d) A numeric admin field saves correctly through the UI: filling
      #ac-rate_rpm and clicking #ac-save persists an int via
      GET /api/admin/config.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("inputs_c7z")
ROOT = Path(__file__).resolve().parents[2]
TOKEN = "y" * 32


def freeport():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def spawn(port, cfg_path):
    env = dict(os.environ)
    env["SATURN_ADMIN_CONFIG_PATH"] = str(cfg_path)
    env["SATURN_ADMIN_PASSWORD"] = "x" * 16
    env["SATURN_ADMIN_TOKEN"] = TOKEN
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
    page.fill("#new1", "inputs-c7z-pw"); page.fill("#new2", "inputs-c7z-pw")
    page.click("#change-submit")
    page.wait_for_url(f"{origin}/", timeout=8_000)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="inputsc7z-"))
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

            # Open admin-configure-page so all numeric fields render.
            # The page is position:fixed but lives inside #discover, so
            # we need that page active for descendants to be visible.
            page.click('.tab[data-tab="discover"]')
            page.evaluate("() => { window.location.hash = 'admin'; }")
            page.wait_for_function(
                "() => { const p = document.getElementById('admin-configure-page');"
                " return p && !p.classList.contains('hidden'); }",
                timeout=4_000,
            )

            counts = page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input'));
                const number = inputs.filter(i => i.type === 'number');
                const decimal = inputs.filter(i =>
                    i.type === 'text' && i.getAttribute('inputmode') === 'decimal'
                );
                return {
                    total: inputs.length,
                    number_typed: number.map(i => i.id || i.name || ''),
                    decimal_count: decimal.length,
                    decimal_sample: decimal.slice(0, 3).map(i => i.id),
                };
            }""")
            results["a_no_number_inputs"] = {
                "number_typed": counts["number_typed"],
                "decimal_count": counts["decimal_count"],
                "ok": len(counts["number_typed"]) == 0
                      and counts["decimal_count"] >= 10,
            }

            # (b) every numeric we know about is text+decimal
            ids = ["ac-rate_rpm", "ac-rate_tpm", "ac-admin_session_ttl_s",
                   "ac-rate_concurrent_per_ip", "ac-max_budget_usd"]
            sample = page.evaluate("""(ids) => {
                return ids.map(id => {
                    const e = document.getElementById(id);
                    return { id, type: e && e.type, im: e && e.getAttribute('inputmode') };
                });
            }""", ids)
            results["b_text_with_inputmode"] = {
                "fields": sample,
                "ok": all(s["type"] == "text" and s["im"] == "decimal"
                          for s in sample),
            }

            # (c) info bubble click reveals description
            target_text = page.evaluate(
                "() => document.querySelector('label[data-info]')?.getAttribute('data-info') || ''"
            )
            page.evaluate(
                "() => document.querySelector('label[data-info] .info-bubble').click()"
            )
            page.wait_for_selector(".info-pop", timeout=3_000)
            popped = page.evaluate(
                "() => document.querySelector('.info-pop')?.textContent || ''"
            )
            results["c_info_bubble_reveals_desc"] = {
                "expected": target_text[:60],
                "got": popped[:60],
                "ok": bool(target_text) and target_text == popped,
            }

            # (d) numeric save round-trip — fill rate_rpm + ac-trust_mode,
            # save, GET /api/admin/config reflects an int.
            page.evaluate("() => document.querySelectorAll('.info-pop').forEach(p => p.remove())")
            page.fill("#ac-rate_rpm", "750")
            # ensure trust_mode select has a valid value before save
            page.evaluate(
                "() => { const s=document.getElementById('ac-trust_mode'); if (s) s.value='tofu'; }"
            )
            page.click("#ac-save")
            time.sleep(0.6)

            api = p.request.new_context(
                base_url=origin,
                extra_http_headers={"authorization": f"Bearer {TOKEN}"},
            )
            saved = api.get("/api/admin/config").json()
            api.dispose()
            results["d_numeric_save_roundtrip"] = {
                "saved_rate_rpm": saved.get("rate_rpm"),
                "type": type(saved.get("rate_rpm")).__name__,
                "ok": saved.get("rate_rpm") == 750,
            }

            page.screenshot(path=str(OUT / "admin_form.png"), full_page=True)
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
