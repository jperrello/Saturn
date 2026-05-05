"""Saturn-qj5.6 — edit-sent-message: truncate-and-regenerate.

Spec (bd Saturn-qj5.6):
- A sent user message must be editable.
- Editing truncates the conversation at that turn (drops the assistant reply
  and any subsequent turns).
- A new assistant turn is generated from the edited message.

Falsifiable surface this contract pins (UI-only, fast, deterministic):
1. Each rendered .msg.user element exposes a visible Edit affordance
   (button / role=button with visible text or aria-label/title containing 'edit').
2. Clicking that Edit affordance reveals an editable input
   (textarea / input / contenteditable) inside the same .msg.user, populated
   with the original message text.

The full truncate-and-regenerate end-to-end (real Ollama + DOM diff after save)
is verified by demo against tests/harness + rodney capture per scaffold —
see CONTRACT.md "Acceptance" item 5.

Real Saturn web + headless Chromium. No mocks.
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from tests.harness import web


ORIGINAL_TEXT = "hello world from brutus qj5.6"


@pytest.fixture(scope="module")
def chat_page_with_user_message():
    with web.serve() as srv, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(srv["origin"])
        page.wait_for_load_state("networkidle")

        chat_tab = page.query_selector('[data-tab="chat"]')
        if chat_tab:
            chat_tab.click()
            page.wait_for_load_state("networkidle")
        accept = page.query_selector("#chat-accept")
        if accept and accept.is_visible():
            try:
                accept.click(timeout=5000)
            except Exception:
                page.evaluate("document.getElementById('chat-accept')?.click()")
            page.wait_for_load_state("networkidle")

        page.evaluate(f"""() => {{
            const messages = document.getElementById('messages');
            if (!messages) return;
            const welcome = document.getElementById('welcome');
            if (welcome) welcome.classList.add('hidden');
            const userDiv = document.createElement('div');
            userDiv.className = 'msg user';
            userDiv.innerHTML = '<div class="prefix">&gt; you</div><div class="bubble">' + {ORIGINAL_TEXT!r}.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</div>';
            messages.appendChild(userDiv);
        }}""")

        try:
            page.wait_for_selector(".msg.user", timeout=5000)
        except Exception:
            pass

        yield page
        browser.close()


def test_user_message_has_edit_affordance(chat_page_with_user_message):
    """Each sent user message must surface a discoverable Edit affordance.
    Hover-revealed is acceptable; the affordance must exist in the DOM after hover."""
    page = chat_page_with_user_message
    user_msg = page.query_selector(".msg.user")
    assert user_msg is not None, "no .msg.user rendered after send — fixture failed to inject the message"
    try:
        user_msg.hover(timeout=2000)
    except Exception:
        pass
    page.wait_for_timeout(200)

    has_edit = page.evaluate("""() => {
        const um = document.querySelector('.msg.user');
        if (!um) return false;
        const candidates = Array.from(um.querySelectorAll('button, [role=button], a'));
        return candidates.some(b => {
            const t = ((b.innerText || '') + ' '
                    + (b.getAttribute('aria-label') || '') + ' '
                    + (b.getAttribute('title') || '')).toLowerCase();
            return /\\bedit\\b/.test(t);
        });
    }""")
    assert has_edit, (
        "no Edit affordance inside .msg.user (looked for button/[role=button]/a whose "
        "visible text, aria-label, or title contains 'edit'). Today the user message "
        "renders only `<div class='prefix'>&gt; you</div><div class='bubble'>…</div>` — "
        "the spec requires a way to invoke edit."
    )


def test_clicking_edit_reveals_editable_input_with_original_text(chat_page_with_user_message):
    """Edit affordance, when clicked, must reveal an editable control inside the .msg.user
    pre-populated with the original message text."""
    page = chat_page_with_user_message
    user_msg = page.query_selector(".msg.user")
    assert user_msg is not None
    try:
        user_msg.hover(timeout=2000)
    except Exception:
        pass
    page.wait_for_timeout(200)

    clicked = page.evaluate("""() => {
        const um = document.querySelector('.msg.user');
        if (!um) return false;
        const btn = Array.from(um.querySelectorAll('button, [role=button], a')).find(b => {
            const t = ((b.innerText || '') + ' '
                    + (b.getAttribute('aria-label') || '') + ' '
                    + (b.getAttribute('title') || '')).toLowerCase();
            return /\\bedit\\b/.test(t);
        });
        if (!btn) return false;
        btn.click();
        return true;
    }""")
    assert clicked, "no Edit button to click inside .msg.user"
    page.wait_for_timeout(300)

    found = page.evaluate(f"""() => {{
        const um = document.querySelector('.msg.user');
        if (!um) return null;
        const inputs = Array.from(um.querySelectorAll('textarea, input[type="text"], input:not([type]), [contenteditable=""], [contenteditable="true"]'));
        for (const i of inputs) {{
            const v = (i.tagName === 'TEXTAREA' || i.tagName === 'INPUT') ? i.value : i.innerText;
            if (v && v.includes({ORIGINAL_TEXT!r})) return {{ tag: i.tagName, len: v.length }};
        }}
        return null;
    }}""")
    assert found is not None, (
        f"Edit click did not reveal an editable input inside .msg.user populated with "
        f"the original text {ORIGINAL_TEXT!r}. Need a textarea / input / [contenteditable]."
    )
