import os
import sys

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_lib import boot, teardown, open_chat, shoot

LABEL = os.environ.get("LABEL", "after")

INJECT = """
const m = document.getElementById('messages');
const w = document.getElementById('welcome');
if (w) w.classList.add('hidden');
const div = document.createElement('div');
div.className = 'msg user';
div.innerHTML = '<div class="prefix">&gt; you</div><div class="bubble">Explain the Saturn V launch sequence in three sentences.</div>';
m.appendChild(div);
if (typeof ensureEditAffordance === 'function') ensureEditAffordance(div);
"""


def main():
    name = boot()
    try:
        with web.serve() as srv, sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900},
                                 device_scale_factor=2)
            page = ctx.new_page()
            open_chat(page, srv["origin"])
            page.evaluate(INJECT)
            page.wait_for_timeout(300)
            shoot(page, ".msg.user", LABEL + "-user-msg", "6")
            edit_btn = page.query_selector(".msg.user .edit-btn")
            if edit_btn:
                edit_btn.click(); page.wait_for_timeout(400)
                shoot(page, ".msg.user", LABEL + "-editing", "6")
            br.close()
    finally:
        teardown(name)


if __name__ == "__main__":
    sys.exit(main() or 0)
