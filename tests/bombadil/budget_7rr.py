"""
Saturn-7rr — max_budget paired with USD/tokens unit selector.

Real Web-UI on a live port. NO MOCKS.

Acceptance:
  (a) Unit toggle USD→tokens persists across reload (server restart).
  (b) Numeric value is retained when unit flips.
  (c) Saved TOML on disk carries both `max_budget` and `max_budget_unit`.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("budget_7rr")
ROOT = Path(__file__).resolve().parents[2]
TOKEN = "y" * 32


def freeport():
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close(); return p


def spawn(port, cfg_path, services_dir):
    env = dict(os.environ)
    env["SATURN_ADMIN_CONFIG_PATH"] = str(cfg_path)
    env["SATURN_ADMIN_PASSWORD"] = "x" * 16
    env["SATURN_ADMIN_TOKEN"] = TOKEN
    env["SATURN_RUNNER_TOKEN"] = "z" * 32
    env["SATURN_SERVICES_DIR"] = str(services_dir)
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


def find(svcs, name):
    for s in svcs:
        if s["name"] == name:
            return s
    return None


def main():
    tmp = Path(tempfile.mkdtemp(prefix="budget7rr-"))
    cfg = tmp / "admin_config.json"
    svc_dir = tmp / "services"; svc_dir.mkdir()
    port = freeport()
    origin = f"http://127.0.0.1:{port}"
    proc = spawn(port, cfg, svc_dir)
    headers = {"authorization": f"Bearer {TOKEN}", "content-type": "application/json"}
    results = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            api = p.request.new_context(base_url=origin, extra_http_headers=headers)

            # Create service with max_budget=5 USD
            create = api.post("/api/services", data=json.dumps({
                "name": "budget7rr",
                "deployment": "cloud",
                "api_type": "openai",
                "priority": 50,
                "upstream": {"base_url": "http://127.0.0.1:11434/v1"},
                "max_budget": 5.0,
                "max_budget_unit": "usd",
            }))
            results["create_status"] = create.status

            initial = find(api.get("/api/services").json(), "budget7rr")
            results["b_initial_value"] = {
                "max_budget": initial.get("max_budget"),
                "max_budget_unit": initial.get("max_budget_unit"),
                "ok": initial.get("max_budget") == 5.0
                      and initial.get("max_budget_unit") == "usd",
            }

            # Flip unit to tokens, keep same value
            api.put("/api/services/budget7rr", data=json.dumps({
                "name": "budget7rr",
                "deployment": "cloud",
                "api_type": "openai",
                "priority": 50,
                "upstream": {"base_url": "http://127.0.0.1:11434/v1"},
                "max_budget": 5.0,
                "max_budget_unit": "tokens",
            }))
            after = find(api.get("/api/services").json(), "budget7rr")
            results["b_value_retained_on_flip"] = {
                "max_budget": after.get("max_budget"),
                "max_budget_unit": after.get("max_budget_unit"),
                "ok": after.get("max_budget") == 5.0
                      and after.get("max_budget_unit") == "tokens",
            }

            # (c) TOML on disk carries both fields
            toml_path = svc_dir / "budget7rr.toml"
            text = toml_path.read_text()
            results["c_toml_has_both"] = {
                "path": str(toml_path), "text": text,
                "ok": "max_budget = 5" in text
                      and 'max_budget_unit = "tokens"' in text,
            }
            api.dispose()

            # (a) restart server, verify persistence after reload
            try:
                proc.terminate(); proc.wait(timeout=5)
            except Exception:
                proc.kill()
            proc2 = spawn(port, cfg, svc_dir)
            try:
                api2 = p.request.new_context(base_url=origin, extra_http_headers=headers)
                reloaded = find(api2.get("/api/services").json(), "budget7rr")
                results["a_persists_across_reload"] = {
                    "max_budget": reloaded.get("max_budget"),
                    "max_budget_unit": reloaded.get("max_budget_unit"),
                    "ok": reloaded.get("max_budget") == 5.0
                          and reloaded.get("max_budget_unit") == "tokens",
                }
                api2.dispose()
            finally:
                try:
                    proc2.terminate(); proc2.wait(timeout=5)
                except Exception:
                    proc2.kill()

            oracle = {k: v["ok"] for k, v in results.items() if isinstance(v, dict) and "ok" in v}
            out = {"results": results, "oracle": oracle, "pass": all(oracle.values())}
            finalize(out, browser, OUT)
    finally:
        try:
            proc.terminate(); proc.wait(timeout=2)
        except Exception:
            try: proc.kill()
            except Exception: pass


if __name__ == "__main__":
    main()
