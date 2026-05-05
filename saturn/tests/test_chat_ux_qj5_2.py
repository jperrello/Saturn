"""Saturn-qj5.2 — Saturn SVG → clearly-labeled Settings button + per-chat popup.

Spec (bd Saturn-qj5.2 + RUN_BRIEF Bucket 1 #2):
- Top-left Saturn SVG is a non-discoverable control. Replace with a clearly-labeled
  Settings button (Nielsen H4 consistency, H6 recognition not recall).
- Clicking opens a per-chat popup containing:
  - Response style (Default / Detailed / Concise / Code)  ← lands here from qj5.1
  - Per-chat model override
  - Current Saturn service

Falsifier: the button is not visibly labeled OR clicking it does not reveal a popup
container that holds all three control families.

Real Saturn web + headless Chromium via tests.harness.web.serve() + playwright.
No mocks.
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from tests.harness import web


@pytest.fixture(scope="module")
def chat_page():
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
        yield page
        browser.close()


def test_chat_settings_button_has_visible_label_text(chat_page):
    """Discoverability — the Settings entry point must carry visible 'Settings' text, not just an SVG.
    Today the button at index.html:268 / :297 contains only the Saturn ring SVG."""
    btns = chat_page.query_selector_all(".chat-shell button, .chat-drawer button, .chat-topbar button")
    visible_labels = []
    for b in btns:
        if not b.is_visible():
            continue
        text = b.inner_text().strip()
        if text:
            visible_labels.append(text.lower())
    assert any("settings" in l for l in visible_labels), (
        f"no chat-tab button shows visible 'Settings' text. "
        f"visible labels: {visible_labels!r}. "
        f"Nielsen H6 (recognition not recall) requires the label, not just aria/title."
    )


def test_settings_click_reveals_popup_with_required_contents(chat_page):
    """Clicking the Settings entry point reveals a single visible container that holds
    all four style options AND a model-override control AND a current-service indicator."""
    # Pick the chat-settings-btn whose bounding box sits inside the viewport
    # (drawer one is positioned offscreen via transform; strip one is in-viewport).
    in_viewport = chat_page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('.chat-settings-btn'));
        const vw = window.innerWidth, vh = window.innerHeight;
        const idx = btns.findIndex(b => {
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.left >= 0 && r.top >= 0 && r.right <= vw && r.bottom <= vh;
        });
        if (idx === -1) return -1;
        btns[idx].click();
        return idx;
    }""")
    assert in_viewport >= 0, (
        "no .chat-settings-btn is in the viewport — entry point not discoverable"
    )
    chat_page.wait_for_timeout(500)

    container = chat_page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        const visible = (el) => {
            if (el.offsetParent === null) {
                const cs = getComputedStyle(el);
                if (cs.position !== 'fixed' || cs.display === 'none' || cs.visibility === 'hidden') return false;
            }
            return true;
        };
        const styleWords = ['default', 'concise', 'detailed', 'code'];
        const candidates = all.filter(el => {
            if (!visible(el)) return false;
            const t = (el.innerText || '').toLowerCase();
            return styleWords.every(w => t.includes(w));
        });
        if (!candidates.length) return null;
        // Pick the smallest (deepest) — that's the popup, not the entire <body>.
        candidates.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
        const popup = candidates[0];
        const txt = (popup.innerText || '').toLowerCase();
        return {
            tag: popup.tagName,
            id: popup.id || null,
            cls: popup.className || null,
            text_len: txt.length,
            has_model: /model/.test(txt),
            has_service: /(service|saturn)/.test(txt),
        };
    }""")
    assert container is not None, (
        "after Settings click, no visible container holds all 4 style options "
        "(Default / Concise / Detailed / Code). The popup is missing."
    )
    assert container["has_model"], (
        f"popup container is missing a model-override control: {container!r}"
    )
    assert container["has_service"], (
        f"popup container is missing a current-service control: {container!r}"
    )
