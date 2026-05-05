"""Saturn-qj5.3 — MCP TOOLS list → popup menu with intuitive Add-MCP flow.

Spec (bd Saturn-qj5.3 + RUN_BRIEF Bucket 1 #3):
- Today, MCP tools live in a persistent inline panel (#tools-panel, index.html:314)
  with a non-obvious "Servers" button (#tools-manage) that toggles a hidden
  #mcp-servers-config sub-block.
- Move the list into a popup (same pattern as qj5.2 Settings popup).
- Surface an obvious "Add MCP server" affordance inside the popup directly —
  no two-click "Servers" detour.

Falsifier:
- The MCP entry button has no discoverable label, OR
- Clicking it does not reveal a positioned popup whose immediate visible content
  contains an obvious "Add MCP server" / "+ MCP server" affordance.

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


def test_mcp_entry_button_has_visible_label(chat_page):
    """The MCP entry must show visible 'MCP' or 'Tools' text — not just an aria-label / wrench SVG.
    Today #tools-toggle has only the wrench (Nielsen H6 violation)."""
    btns = chat_page.query_selector_all("#chat-shell button, .chat-topbar button")
    visible_labels = []
    for b in btns:
        if not b.is_visible():
            continue
        text = b.inner_text().strip()
        if text:
            visible_labels.append(text.lower())
    assert any(("mcp" in l or "tools" in l) for l in visible_labels), (
        f"no chat-tab button shows visible 'MCP' or 'Tools' text. "
        f"visible labels: {visible_labels!r}. "
        f"aria-label / title alone do not satisfy Nielsen H6 (recognition not recall)."
    )


def test_mcp_click_reveals_popup_with_add_server(chat_page):
    """Clicking the MCP entry reveals a positioned popup whose immediate visible content
    contains an 'Add MCP server' / '+ MCP server' affordance — no two-click 'Servers' detour."""
    clicked = chat_page.evaluate("""() => {
        const candidates = Array.from(document.querySelectorAll('#chat-shell button, .chat-topbar button')).filter(b => {
            const r = b.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('title') || '')).toLowerCase();
            return /mcp|tools/.test(t);
        });
        const vw = window.innerWidth, vh = window.innerHeight;
        const inView = candidates.find(b => {
            const r = b.getBoundingClientRect();
            return r.left >= 0 && r.top >= 0 && r.right <= vw && r.bottom <= vh;
        });
        if (!inView) return null;
        inView.click();
        return inView.id || inView.className || 'unknown';
    }""")
    assert clicked, "no in-viewport MCP/Tools entry button found in chat tab"
    chat_page.wait_for_timeout(500)

    popup = chat_page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        const visible = (el) => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return false;
            const cs = getComputedStyle(el);
            return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
        };
        for (const el of all) {
            if (!visible(el)) continue;
            const cs = getComputedStyle(el);
            if (cs.position !== 'absolute' && cs.position !== 'fixed') continue;
            const txt = (el.innerText || '').toLowerCase();
            const hasAdd = /add\\s+mcp/.test(txt)
                        || /add\\s+server/.test(txt)
                        || /\\+\\s*mcp/.test(txt)
                        || /\\+\\s*server/.test(txt)
                        || /new\\s+mcp/.test(txt);
            if (hasAdd && txt.length < 4000) {
                return { tag: el.tagName, id: el.id || null, cls: el.className || null, position: cs.position, text_len: txt.length };
            }
        }
        return null;
    }""")
    assert popup is not None, (
        "after MCP click, no positioned (absolute/fixed) popup surfaces a discoverable "
        "'Add MCP server' / '+ MCP server' / 'New MCP …' affordance directly. "
        "The current #tools-panel is inline (not positioned) and hides the add form behind a 'Servers' button."
    )
