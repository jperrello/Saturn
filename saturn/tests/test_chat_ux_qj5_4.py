"""Saturn-qj5.4 — replace 5 unlabeled icons with a '+' menu (Claude-style).

Spec (bd Saturn-qj5.4 + RUN_BRIEF Bucket 1 #4):
- Today the chat-input row hosts 5 .fab buttons (index.html:380-385):
  #file-upload-btn, #thinking-toggle, #export-json, #export-md, #tools-toggle.
  All show only an SVG; none has a visible label.
- Replace with a single '+' menu. FINAL menu items (DO NOT add others):
  - Attach file/photo
  - MCP tools / Connectors
- Style picker is NOT here — it lives in the Settings popup (qj5.2).

Falsifier:
- More than one entry-point button remains above the chat input next to #send-btn, OR
- No '+' affordance opens a menu, OR
- The opened menu still surfaces the removed-by-spec legacy items
  (thinking, export-json, export-markdown).

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


def test_chat_input_row_has_single_entry_button(chat_page):
    """The 5-fab cluster above the chat input must collapse to a single '+' menu entry next to #send-btn."""
    count = chat_page.evaluate("""() => {
        const area = document.querySelector('.chat-input-fabs, .chat-input-float, .chat-input-area');
        if (!area) return null;
        const btns = Array.from(area.querySelectorAll('button')).filter(b => b.offsetParent !== null);
        return btns.filter(b => b.id !== 'send-btn').length;
    }""")
    assert count is not None, "no chat-input area resolved (.chat-input-fabs / .chat-input-float / .chat-input-area)"
    assert count <= 1, (
        f"expected at most one entry-point button above the chat input (the '+'); "
        f"found {count}. Today the 5 unlabeled .fab icons "
        f"(#file-upload-btn, #thinking-toggle, #export-json, #export-md, #tools-toggle) "
        f"sit alongside #send-btn — qj5.4 collapses them into a single '+' menu."
    )


def test_plus_menu_reveals_only_final_items(chat_page):
    """Clicking the '+' entry reveals a menu whose items are scoped to the FINAL list:
    Attach file/photo + MCP tools/Connectors. No legacy thinking/export items."""
    plus_clicked = chat_page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('button'));
        const candidate = all.find(b => {
            if (b.offsetParent === null) return false;
            const text = (b.innerText || '').trim();
            const aria = (b.getAttribute('aria-label') || '').toLowerCase();
            const title = (b.getAttribute('title') || '').toLowerCase();
            return text === '+' || /add\\s*menu|plus|attach\\s*menu|attachments?\\s*menu/.test(aria + ' ' + title);
        });
        if (!candidate) return false;
        candidate.click();
        return true;
    }""")
    assert plus_clicked, (
        "no '+' menu button found in the chat-input area. Visible label '+' (or aria/title 'add menu', "
        "'plus', 'attach menu', 'attachments menu') is required so users discover the affordance."
    )
    chat_page.wait_for_timeout(500)

    menus = chat_page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        const out = [];
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
            const items = Array.from(el.querySelectorAll('[role=menuitem], li, button, a'))
                .filter(c => visible(c) && (c.innerText || '').trim());
            if (items.length >= 2 && items.length <= 8) {
                out.push({
                    container: el.tagName + (el.id ? '#' + el.id : ''),
                    items: items.map(c => (c.innerText || '').trim().toLowerCase()),
                });
            }
        }
        return out;
    }""")
    assert menus, "after '+' click, no positioned menu container with 2-8 items appeared"

    # Smallest = likeliest the + menu (not the qj5.2 settings popup).
    menus.sort(key=lambda c: len(c["items"]))
    menu = menus[0]
    items = menu["items"]

    has_attach = any(("attach" in it or "file" in it or "photo" in it or "upload" in it) for it in items)
    has_mcp    = any(("mcp"   in it or "connector" in it or "tool" in it) for it in items)
    legacy = [it for it in items if any(w in it for w in ("thinking", "export", "json", "markdown"))]

    assert has_attach, f"'+' menu missing Attach file/photo item; items={items!r}"
    assert has_mcp,    f"'+' menu missing MCP tools / Connectors item; items={items!r}"
    assert not legacy, (
        f"'+' menu still surfaces legacy items the spec explicitly removed: {legacy!r}. "
        f"FINAL list is exactly: Attach file/photo, MCP tools/Connectors."
    )
