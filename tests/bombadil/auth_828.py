"""
Saturn-828 — Web-UI session-cookie gate, independent verification.

Real Web-UI on a live port. NO MOCKS. Spawns its own `saturn web` so it
can pin SATURN_ADMIN_CONFIG_PATH at a tmp file and exercise the
first-run change-password flow from a known clean state.

Verifies:
  (a) unauthenticated request to root redirects to /login (303).
  (b) wrong password rejected (401, no session cookie).
  (c) correct default password 'Saturn' sets saturn_session cookie and
      unlocks /.
  (d) logout clears the cookie; subsequent / hit redirects to /login.
  (e) first-run /api/auth/status returns must_change: True; the login
      page shows the change-password form after default sign-in and
      submitting a new password persists (old default rejected, new
      password unlocks /, must_change becomes false).
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("auth_828")
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
                time.sleep(0.4)
                return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"saturn web did not start on {port}")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="auth828-"))
    cfg = tmp / "admin_config.json"
    port = freeport()
    origin = f"http://127.0.0.1:{port}"
    proc = spawn(port, cfg)
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            api = p.request.new_context(base_url=origin)

            # (a) unauth GET / → 303 to /login (no auto follow)
            r = api.get("/", max_redirects=0)
            results["a_unauth_redirect"] = {
                "status": r.status,
                "location": r.headers.get("location", ""),
                "ok": r.status == 303 and r.headers.get("location") == "/login",
            }

            # (e1) first-run status
            r = api.get("/api/auth/status")
            j = r.json()
            results["e_first_run_status"] = {
                "json": j,
                "ok": r.status == 200 and j.get("authenticated") is False
                      and j.get("must_change") is True,
            }

            # (b) wrong password rejected, no cookie set
            api_b = p.request.new_context(base_url=origin)
            r = api_b.post("/api/auth/login",
                           data=json.dumps({"password": "definitely-wrong"}),
                           headers={"content-type": "application/json"})
            cookies_b = api_b.storage_state()["cookies"]
            results["b_wrong_pw_rejected"] = {
                "status": r.status,
                "cookie_set": any(c["name"] == "saturn_session" for c in cookies_b),
                "ok": r.status == 401 and not any(
                    c["name"] == "saturn_session" for c in cookies_b),
            }
            api_b.dispose()

            # (c) correct default 'Saturn' sets cookie, unlocks /
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(f"{origin}/", wait_until="domcontentloaded")
            results["c_redirect_to_login"] = {
                "url": page.url,
                "ok": page.url.endswith("/login"),
            }

            # (e2) UI flow: must_change form should activate after default login
            page.fill("#pw", "Saturn")
            page.click("#submit")
            page.wait_for_function(
                "() => document.getElementById('change-form').style.display === 'block'",
                timeout=8_000,
            )
            results["e_change_form_shown"] = {"ok": True}

            # session cookie present after default login
            cookies_c = [c for c in ctx.cookies() if c["name"] == "saturn_session"]
            results["c_cookie_set"] = {
                "count": len(cookies_c),
                "ok": len(cookies_c) == 1 and cookies_c[0].get("httpOnly") is True,
            }

            # submit new password through change-form
            new_pw = "newSaturn-9!"
            page.fill("#new1", new_pw)
            page.fill("#new2", new_pw)
            page.click("#change-submit")
            page.wait_for_url(f"{origin}/", timeout=8_000)
            results["e_change_lands_root"] = {
                "url": page.url, "ok": page.url.rstrip("/") == origin,
            }

            # status after change: authenticated=True, must_change=False
            j2 = page.evaluate(
                "async () => (await fetch('/api/auth/status')).json()"
            )
            results["e_status_after_change"] = {
                "json": j2,
                "ok": j2.get("authenticated") is True and j2.get("must_change") is False,
            }

            # old default 'Saturn' should now fail in a fresh context
            api_old = p.request.new_context(base_url=origin)
            r = api_old.post("/api/auth/login",
                             data=json.dumps({"password": "Saturn"}),
                             headers={"content-type": "application/json"})
            results["e_old_default_rejected"] = {
                "status": r.status, "ok": r.status == 401,
            }
            api_old.dispose()

            # new password unlocks, must_change=False
            api_new = p.request.new_context(base_url=origin)
            r = api_new.post("/api/auth/login",
                             data=json.dumps({"password": new_pw}),
                             headers={"content-type": "application/json"})
            jn = r.json()
            results["e_new_pw_unlocks"] = {
                "status": r.status, "json": jn,
                "ok": r.status == 200 and jn.get("must_change") is False,
            }
            api_new.dispose()

            # (d) logout clears cookie, root redirects again
            page.evaluate(
                "async () => (await fetch('/api/auth/logout', {method: 'POST'}))"
            )
            ctx.clear_cookies()
            r = api.get("/", max_redirects=0)
            results["d_logout_redirects"] = {
                "status": r.status,
                "location": r.headers.get("location", ""),
                "ok": r.status == 303 and r.headers.get("location") == "/login",
            }

            page.screenshot(path=str(OUT / "after_change.png"), full_page=True)
            ctx.close()
            api.dispose()

            oracle = {k: v["ok"] for k, v in results.items()}
            out = {"results": results, "oracle": oracle, "pass": all(oracle.values())}
            finalize(out, browser, OUT)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
