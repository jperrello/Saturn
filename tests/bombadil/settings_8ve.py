"""
Saturn-8ve — settings rewrite live-diff.

Real Web-UI on a live port + real Ollama qwen2.5:0.5b. NO MOCKS.

Each of the 11 Tier S params must demonstrably affect /api/chat output:
  baseline:  temperature, top_p, top_k, max_tokens, system_prompt
  penalties: frequency_penalty, presence_penalty, repeat_penalty, min_p
  control:   seed (determinism + plumbing), stop

Pattern (per gullivan rough-pass note): pin seed, send identical prompt
twice, vary the param under test between calls, assert outputs differ.
Plus seed self-test:
  same prompt + same params + diff seeds → outputs differ
  same prompt + same params + same seed twice → outputs identical

Any param whose two variants produce identical output is flagged in the
result and (per athena) reported separately so a follow-up bead can be
filed for hardener.
"""

import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import results_dir, finalize

OUT = results_dir("settings_8ve")
ROOT = Path(__file__).resolve().parents[2]
TOKEN = "y" * 32

MODEL = "qwen2.5:0.5b"
PROMPT = "Write a single short sentence about dogs."
BASE = {
    "temperature": 0.8, "top_p": 0.9, "top_k": 40,
    "max_tokens": 50, "seed": 42,
}


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


def call_chat(api, system, params):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": PROMPT})
    payload = {
        "service": "ollama8ve",
        "model": MODEL,
        "messages": msgs,
        "stream": False,
        **params,
    }
    r = api.post("/api/chat", data=json.dumps(payload))
    if r.status != 200:
        return f"<HTTP {r.status}: {r.text()[:200]}>"
    j = r.json()
    return j.get("choices", [{}])[0].get("message", {}).get("content", "") or ""


def diff_param(api, label, params_a, params_b, sys_a=None, sys_b=None):
    a = call_chat(api, sys_a, params_a)
    b = call_chat(api, sys_b, params_b)
    return {
        "label": label,
        "out_a": a[:160], "out_b": b[:160],
        "differ": a != b,
    }


def main():
    tmp = Path(tempfile.mkdtemp(prefix="settings8ve-"))
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
            api = p.request.new_context(
                base_url=origin, extra_http_headers=headers, timeout=120_000,
            )

            # register the Ollama service so /api/chat can resolve it
            api.post("/api/services", data=json.dumps({
                "name": "ollama8ve",
                "deployment": "cloud",
                "api_type": "ollama",
                "priority": 50,
                "upstream": {"base_url": "http://127.0.0.1:11434/v1"},
            }))

            # --- seed self-test ---
            same_a = call_chat(api, None, dict(BASE, seed=42))
            same_b = call_chat(api, None, dict(BASE, seed=42))
            diff_x = call_chat(api, None, dict(BASE, seed=42))
            diff_y = call_chat(api, None, dict(BASE, seed=999))
            results["seed_determinism"] = {
                "same_seed_match": same_a == same_b,
                "diff_seed_differ": diff_x != diff_y,
                "out_same_a": same_a[:80], "out_same_b": same_b[:80],
                "out_diff_x": diff_x[:80], "out_diff_y": diff_y[:80],
                "ok": same_a == same_b and diff_x != diff_y,
            }

            # --- per-param live diff (10 others) ---
            param_tests = []

            # 1. temperature
            param_tests.append(diff_param(api, "temperature",
                dict(BASE, temperature=0.0), dict(BASE, temperature=1.5)))
            # 2. top_p
            param_tests.append(diff_param(api, "top_p",
                dict(BASE, top_p=0.1), dict(BASE, top_p=1.0)))
            # 3. top_k
            param_tests.append(diff_param(api, "top_k",
                dict(BASE, top_k=1), dict(BASE, top_k=100)))
            # 4. max_tokens
            param_tests.append(diff_param(api, "max_tokens",
                dict(BASE, max_tokens=8), dict(BASE, max_tokens=80)))
            # 5. system_prompt — varied via system message
            param_tests.append(diff_param(api, "system_prompt",
                dict(BASE), dict(BASE),
                sys_a="Reply with a single word.",
                sys_b="Reply with three sentences in French."))
            # 6. frequency_penalty
            param_tests.append(diff_param(api, "frequency_penalty",
                dict(BASE, frequency_penalty=0.0),
                dict(BASE, frequency_penalty=2.0)))
            # 7. presence_penalty
            param_tests.append(diff_param(api, "presence_penalty",
                dict(BASE, presence_penalty=0.0),
                dict(BASE, presence_penalty=2.0)))
            # 8. repeat_penalty (UI label: repetition_penalty)
            param_tests.append(diff_param(api, "repeat_penalty",
                dict(BASE, repeat_penalty=1.0),
                dict(BASE, repeat_penalty=2.0)))
            # 9. min_p
            param_tests.append(diff_param(api, "min_p",
                dict(BASE, min_p=0.0), dict(BASE, min_p=0.9)))
            # 10. stop
            param_tests.append(diff_param(api, "stop",
                dict(BASE), dict(BASE, stop=["the", "a", " "])))

            results["per_param"] = {
                "tests": param_tests,
                "differ_count": sum(1 for t in param_tests if t["differ"]),
                "total": len(param_tests),
                "ok": all(t["differ"] for t in param_tests),
            }
            results["non_diff_params"] = [
                t["label"] for t in param_tests if not t["differ"]
            ]

            api.dispose()

            oracle = {
                "seed_determinism": results["seed_determinism"]["ok"],
                "per_param_all_differ": results["per_param"]["ok"],
            }
            out = {"results": results, "oracle": oracle, "pass": all(oracle.values())}
            finalize(out, browser, OUT)
    finally:
        try:
            proc.terminate(); proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
