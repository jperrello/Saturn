"""Saturn-qj5.1 — remove top-right response-style pill from Chat tab.

Spec: the four-option pill (Default/Concise/Detailed/Code) at the top-right of the Chat tab
must be removed. Style selection moves to the per-chat Settings popup (qj5.2 — separate bead,
not asserted here).

Falsifier: any of the assertions below holding means the pill is still in the chat-tab strip.

Approach: real Saturn web via tests.harness.web.serve(); real headless Chromium via playwright.
No mocks — same surface a user sees.
"""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from tests.harness import web


@pytest.fixture(scope="module")
def chat_page():
    with web.serve() as srv, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(srv["origin"])
        page.wait_for_load_state("networkidle")
        chat_tab = page.query_selector('[data-tab="chat"]')
        if chat_tab:
            chat_tab.click()
            page.wait_for_load_state("networkidle")
        yield page
        browser.close()


def test_style_pill_removed_by_id(chat_page):
    """The legacy pill at index.html:299 has id='style-select'. It must not exist anywhere on the page."""
    el = chat_page.query_selector("#style-select")
    assert el is None, "#style-select still present in DOM — pill was not removed"


def test_no_style_select_in_top_strip(chat_page):
    """Even if relocated/renamed, no <select> in the top chat strip should expose Default/Concise/Detailed/Code together."""
    selects = chat_page.query_selector_all(".strip-right select, .chat-strip select")
    offending = []
    for s in selects:
        opts = [o.inner_text().strip().lower() for o in s.query_selector_all("option")]
        opt_set = set(opts)
        if {"default", "concise", "detailed", "code"} <= opt_set:
            offending.append(opts)
    assert not offending, (
        f"top-strip <select> still exposes the response-style pill options: {offending}"
    )


