"""
Saturn-cbt.2.1 — long-message UX contract.

Four contracts probed against the live Web-UI with a real backend (Ollama
qwen2.5:0.5b). No mocks. Token-count proxy: 4k ~= 16000 chars, 32k ~=
128000 chars (per parent bead).

  C1. ~4k-token user input — keystroke latency in #chat-input <= 50ms p95
      across N synthetic keystrokes appended after pre-fill.
  C2. ~32k-token user input — clicking #send-btn must not block the main
      thread > 500ms (measured via setTimeout(0) latency straddling the
      click and via click->next-rAF time).
  C3. ~4k-token streamed assistant — bubble grows in >= 4 distinct
      progressive updates (no single drop).
  C4. ~32k-token streamed assistant — same chunked-growth assertion AND
      programmatic scroll mid-stream succeeds (scrollTop changes after
      we set it to a non-bottom value while cursor is still present).

C3/C4 acknowledge the parent bead's documented model-size caveat: qwen2.5
:0.5b will rarely emit a true 32k-token completion. We request a verbose
response with max_tokens raised, and verify the cadence properties on
whatever the model produces; the chunked-growth assertion is the
load-bearing UX claim, not the absolute output length.

Pass 1: spec lands, runs against current main, captures red baseline.
Pass 2: re-runs after hardener; expected green.
"""

import json, os, socket, subprocess, sys, tempfile, time, statistics
from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import (
    gate_init_script, inject_manual_endpoint, open_chat_with_endpoint,
    attach_console_error_collector, results_dir,
)

OUT = results_dir("longmsg_cbt21")
ROOT = Path(__file__).resolve().parents[2]
GATE_PW_NEW = "cbt21-verify-pw-9"

CHARS_4K = 16000
CHARS_32K = 128000
KEYSTROKE_BUDGET_MS = 50
SEND_BLOCK_BUDGET_MS = 500
MIN_PROGRESSIVE_UPDATES = 4
SAMPLE_INTERVAL_MS = 80


def _filler(n):
    base = "lorem ipsum dolor sit amet consectetur adipiscing elit "
    return (base * ((n // len(base)) + 1))[:n]


def _measure_keystrokes(page, count=30):
    # measure inside the page: dispatch input events, await next rAF,
    # report dispatch->paint-ready latency. CDP roundtrips are NOT
    # what we care about — user-perceived keystroke latency is.
    # measure synchronous JS work per keystroke (value mutation + input
    # event handler chain). Excludes paint — headless chromium throttles
    # rAF unreliably (see longstream_3t8.py oracle note). Synchronous
    # main-thread time IS what determines whether the next keystroke can
    # be processed; >50ms here means the input bar is laggy.
    samples = page.evaluate("""
        (n) => {
            const el = document.getElementById('chat-input');
            el.focus();
            const xs = [];
            for (let i = 0; i < n; i++) {
                const ch = String.fromCharCode(97 + (i % 26));
                const t0 = performance.now();
                el.value = el.value + ch;
                el.dispatchEvent(new InputEvent('input', { bubbles: true, data: ch, inputType: 'insertText' }));
                xs.push(performance.now() - t0);
            }
            return xs;
        }
    """, count)
    return samples


def _p95(xs):
    if not xs: return 0.0
    s = sorted(xs)
    return s[max(0, int(len(s) * 0.95) - 1)]


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
    page.add_init_script(gate_init_script({"saturn-model-params": {"max_tokens": 32000}}))
    _login(page, origin)
    page.goto(origin, wait_until="domcontentloaded")
    inject_manual_endpoint(page)
    open_chat_with_endpoint(page)


def c1_keystroke_latency(p, origin):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    page.evaluate(
        "(t) => { const el = document.getElementById('chat-input');"
        " el.value = t; el.dispatchEvent(new Event('input', {bubbles:true})); }",
        _filler(CHARS_4K),
    )
    samples = _measure_keystrokes(page, count=30)
    page.screenshot(path=str(OUT / "c1_after.png"), full_page=False)
    browser.close()
    return {
        "n": len(samples),
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(_p95(samples), 2),
        "max_ms": round(max(samples), 2) if samples else 0,
        "pass": _p95(samples) <= KEYSTROKE_BUDGET_MS,
    }


def c2_send_block(p, origin):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    _setup(page, origin)
    page.evaluate(
        "(t) => { const el = document.getElementById('chat-input');"
        " el.value = t; el.dispatchEvent(new Event('input', {bubbles:true})); }",
        _filler(CHARS_32K),
    )
    metrics = page.evaluate("""
        async () => {
            const start = performance.now();
            let rafFired = 0;
            requestAnimationFrame(() => { rafFired = performance.now(); });
            document.getElementById('send-btn').click();
            const t0 = performance.now();
            await new Promise(r => setTimeout(r, 0));
            const t1 = performance.now();
            await new Promise(r => requestAnimationFrame(() => r()));
            const t2 = performance.now();
            return {
                clickToTimer0: t1 - t0,
                clickToRaf: t2 - start,
            };
        }
    """)
    page.screenshot(path=str(OUT / "c2_after.png"), full_page=False)
    browser.close()
    block_ms = max(metrics["clickToTimer0"], metrics["clickToRaf"])
    return {
        "click_to_timer0_ms": round(metrics["clickToTimer0"], 2),
        "click_to_raf_ms": round(metrics["clickToRaf"], 2),
        "block_ms": round(block_ms, 2),
        "pass": block_ms <= SEND_BLOCK_BUDGET_MS,
    }


def _stream_and_sample(page, prompt, hard_timeout_s, scroll_probe=False, pad_dom=False):
    if pad_dom:
        # Force the messages container to overflow so the scroll probe is
        # meaningful even if the model response is short. We append filler
        # children directly to #messages — the assistant stream still
        # appends after them.
        page.evaluate("""
            () => {
                const msgs = document.getElementById('messages');
                if (!msgs) return;
                for (let i = 0; i < 30; i++) {
                    const d = document.createElement('div');
                    d.className = 'msg user';
                    d.style.minHeight = '60px';
                    d.textContent = 'pad ' + i + ' ' + 'x'.repeat(200);
                    msgs.appendChild(d);
                }
                msgs.scrollTop = msgs.scrollHeight;
            }
        """)
    page.fill("#chat-input", prompt)
    page.click("#send-btn")
    page.wait_for_selector(".msg.assistant .cursor", timeout=15_000)
    lens = []
    scrolls = []
    scroll_probe_result = None
    deadline = time.monotonic() + hard_timeout_s
    probed = False
    while time.monotonic() < deadline:
        m = page.evaluate("""
            () => {
                const b = document.querySelector('.msg.assistant:last-of-type .bubble');
                const msgs = document.getElementById('messages');
                return {
                    len: b ? (b.textContent || '').length : 0,
                    scrollTop: msgs ? msgs.scrollTop : 0,
                    scrollHeight: msgs ? msgs.scrollHeight : 0,
                    clientHeight: msgs ? msgs.clientHeight : 0,
                    cursor: !!document.querySelector('.msg.assistant .cursor'),
                };
            }
        """)
        lens.append(m["len"])
        scrolls.append(m["scrollTop"])
        overflow = m["scrollHeight"] - m["clientHeight"]
        if scroll_probe and not probed and overflow > 300 and m["len"] > 0:
            before = m["scrollTop"]
            target = 0
            page.evaluate(
                "(t) => { document.getElementById('messages').scrollTop = t; }",
                target,
            )
            time.sleep(0.15)
            after = page.evaluate(
                "() => document.getElementById('messages').scrollTop"
            )
            scroll_probe_result = {
                "before": before, "set_to": target, "after": after,
                "overflow_px": overflow,
                "moved": abs(after - before) > 50 and abs(after - target) < 50,
            }
            probed = True
        if not m["cursor"] and lens and lens[-1] > 0:
            break
        time.sleep(SAMPLE_INTERVAL_MS / 1000.0)
    distinct = sum(1 for i in range(1, len(lens)) if lens[i] > lens[i-1])
    return {
        "samples": len(lens),
        "final_len": lens[-1] if lens else 0,
        "distinct_growth_steps": distinct,
        "scroll_probe": scroll_probe_result,
    }


def c3_stream_4k(p, origin):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errs = []
    attach_console_error_collector(page, errs)
    _setup(page, origin)
    res = _stream_and_sample(
        page,
        "Write a story about a wizard. Be very verbose, at least 4000 words. "
        "Describe many rooms, characters, books. Do not stop early.",
        hard_timeout_s=90,
    )
    page.screenshot(path=str(OUT / "c3_after.png"), full_page=False)
    browser.close()
    res["console_errors"] = errs
    res["pass"] = res["distinct_growth_steps"] >= MIN_PROGRESSIVE_UPDATES and res["final_len"] > 0
    return res


def c4_stream_32k(p, origin):
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errs = []
    attach_console_error_collector(page, errs)
    _setup(page, origin)
    # Per parent bead note: qwen2.5:0.5b cannot reliably emit ~32k tokens.
    # We use the same verbose-eliciting prompt as C3 plus pre-padded DOM
    # so the messages container is genuinely scrollable, then probe both
    # chunked growth and mid-stream scroll-pin release. The chunked-growth
    # assertion is the load-bearing UX claim (parent bead).
    res = _stream_and_sample(
        page,
        "Write a long story about a wizard. Be very verbose, at least 4000 words. "
        "Describe many rooms, characters, books. Do not stop early.",
        hard_timeout_s=180,
        scroll_probe=True,
        pad_dom=True,
    )
    page.screenshot(path=str(OUT / "c4_after.png"), full_page=False)
    browser.close()
    res["console_errors"] = errs
    sp = res.get("scroll_probe") or {}
    res["pass"] = (
        res["distinct_growth_steps"] >= MIN_PROGRESSIVE_UPDATES
        and res["final_len"] > 0
        and bool(sp.get("moved"))
    )
    return res


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cbt21-"))
    cfg = tmp / "admin.json"
    port = _freeport()
    origin = f"http://localhost:{port}"
    proc = _spawn(port, cfg)
    out = {}
    try:
        with sync_playwright() as p:
            for key, fn in [
                ("c1_keystroke_4k", c1_keystroke_latency),
                ("c2_send_block_32k", c2_send_block),
                ("c3_stream_4k", c3_stream_4k),
                ("c4_stream_32k", c4_stream_32k),
            ]:
                try:
                    out[key] = fn(p, origin)
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
