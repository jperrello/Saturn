"""
Bombadil/Playwright shared helpers for Saturn Web-UI scenarios.

Every scenario in this directory does the same dance to get a usable chat
state: gate dismissal, manual-endpoint injection, service+model dropdown
selection, then a bounded send/wait. Centralized here so the next UI bead
can be 20 lines of oracle code instead of 60 lines of boilerplate.

Conventions:
  - PORT defaults to $SATURN_PORT (39301), settable via env.
  - LOCAL_OLLAMA points at http://localhost:11434/v1.
  - DEFAULT_MODEL is qwen2.5:0.5b — small, present on the dev box.
  - results_dir(name) returns tests/bombadil/results/<name>/, created.
  - finalize(out, browser, results_dir) writes result.json + exits with
    the oracle pass code so callers don't repeat the boilerplate.

No mocks. Real saturn web. Real backend.
"""

import json, os, sys, time
from pathlib import Path

PORT = int(os.environ.get("SATURN_PORT", "39301"))
ORIGIN = f"http://localhost:{PORT}"
LOCAL_OLLAMA = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:0.5b"
RESULTS_ROOT = Path(__file__).parent / "results"


def results_dir(name):
    p = RESULTS_ROOT / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def gate_init_script(extra_localstorage=None):
    """JS run on every navigation: dismiss chat gate + seed model params.
    `extra_localstorage` is an optional {key: json-stringifiable} dict
    merged in alongside the defaults."""
    items = {
        "chat-accepted": "1",
        "saturn-model-params": json.dumps({"max_tokens": 4000}),
    }
    if extra_localstorage:
        for k, v in extra_localstorage.items():
            items[k] = v if isinstance(v, str) else json.dumps(v)
    lines = "\n".join(
        f"window.localStorage.setItem({json.dumps(k)}, {json.dumps(v)});"
        for k, v in items.items()
    )
    return lines


def inject_manual_endpoint(page, name="local", url=LOCAL_OLLAMA, api_type="openai"):
    """Add a manual endpoint via the Configure form. Works on any tab —
    the form's hidden, but its handler still fires."""
    page.wait_for_selector("#ep-add", state="attached", timeout=10_000)
    page.evaluate(
        "(args) => {"
        "  document.getElementById('ep-name').value = args.name;"
        "  document.getElementById('ep-url').value = args.url;"
        "  document.getElementById('ep-type').value = args.api_type;"
        "  document.getElementById('ep-add').click();"
        "}",
        {"name": name, "url": url, "api_type": api_type},
    )


def open_chat_with_endpoint(page, endpoint_name="local", model=DEFAULT_MODEL):
    """Click Chat tab, select the manual endpoint and model. Waits for
    the dropdowns to populate. Caller is expected to have already
    invoked inject_manual_endpoint()."""
    page.click('.tab[data-tab="chat"]')
    target = f"__manual__:{endpoint_name}"
    page.wait_for_function(
        f"() => Array.from(document.getElementById('service-select').options)"
        f".some(o => o.value === {json.dumps(target)})",
        timeout=10_000,
    )
    page.select_option("#service-select", target)
    page.wait_for_function(
        f"() => Array.from(document.getElementById('model-select').options)"
        f".some(o => o.value === {json.dumps(model)})",
        timeout=15_000,
    )
    page.select_option("#model-select", model)


def setup_chat_page(page, endpoint_name="local", model=DEFAULT_MODEL,
                     extra_localstorage=None):
    """One-call setup: init script → goto → endpoint → chat tab + selects.
    Returns nothing; mutates the page."""
    page.add_init_script(gate_init_script(extra_localstorage))
    page.goto(ORIGIN, wait_until="domcontentloaded")
    inject_manual_endpoint(page, name=endpoint_name)
    open_chat_with_endpoint(page, endpoint_name=endpoint_name, model=model)


def send_message(page, text, wait_complete=True, stream_timeout_s=60):
    """Fill #chat-input, click send, wait for the cursor to appear. If
    wait_complete, also wait for cursor to disappear and send-btn to
    recover from "Stop" → enabled."""
    page.fill("#chat-input", text)
    page.click("#send-btn")
    page.wait_for_selector(".msg.assistant .cursor", timeout=10_000)
    if not wait_complete:
        return
    deadline = time.monotonic() + stream_timeout_s
    while time.monotonic() < deadline:
        if not page.evaluate("() => !!document.querySelector('.msg.assistant .cursor')"):
            break
        time.sleep(0.2)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if page.evaluate(
            "() => !document.getElementById('send-btn').disabled && "
            "document.getElementById('send-btn').textContent.trim().toLowerCase() !== 'stop'"
        ):
            break
        time.sleep(0.1)


def chat_state(page):
    """Return DOM .msg count, stored chat.messages count, and last user
    text from localStorage `saturn-chats`. Used by the edit_ao6 family
    to assert DOM/storage consistency."""
    return page.evaluate("""
        () => {
            const dom = document.querySelectorAll('#messages .msg').length;
            let stored = 0, lastUser = '';
            try {
                const raw = localStorage.getItem('saturn-chats');
                if (raw) {
                    const chats = JSON.parse(raw);
                    if (chats[0]) {
                        stored = chats[0].messages.length;
                        for (let i = chats[0].messages.length - 1; i >= 0; i--) {
                            if (chats[0].messages[i].role === 'user') {
                                lastUser = chats[0].messages[i].text;
                                break;
                            }
                        }
                    }
                }
            } catch {}
            return { dom, stored, lastUser };
        }
    """)


def toast_text(page):
    return page.evaluate(
        "() => { const t=document.getElementById('toast'); "
        "return t && !t.classList.contains('hidden') ? t.textContent : ''; }"
    )


def reset_toast(page):
    page.evaluate("() => document.getElementById('toast').classList.add('hidden')")


def filter_background_console_errors(text):
    """Drop the noisy 401s on /api/services + /api/admin that fire on
    page load when no admin token is set. Unrelated to any chat-path
    bead under test."""
    if "401 (Unauthorized)" in text: return True
    if "/api/services" in text or "/api/admin" in text: return True
    return False


def attach_console_error_collector(page, errors_list):
    """Wires `page.on('console', ...)` to push filtered errors into
    `errors_list`. Caller owns the list."""
    def _onmsg(msg):
        if msg.type != "error": return
        if filter_background_console_errors(msg.text): return
        errors_list.append({"type": msg.type, "text": msg.text})
    page.on("console", _onmsg)


def finalize(out, browser, out_dir, screenshot_path=None):
    """Write result.json, print to stdout, close browser, exit with
    pass/fail code. Pass `screenshot_path` if the caller already took
    one; otherwise no screenshot is written here."""
    (out_dir / "result.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    try:
        browser.close()
    except Exception:
        pass
    sys.exit(0 if out.get("pass") else 1)
