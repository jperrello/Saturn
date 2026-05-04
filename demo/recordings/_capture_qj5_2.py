import os
import sys

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_lib import boot, teardown, open_chat, shoot

LABEL = os.environ.get("LABEL", "after")


def main():
    name = boot()
    try:
        with web.serve() as srv, sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900},
                                 device_scale_factor=2)
            page = ctx.new_page()
            open_chat(page, srv["origin"])
            shoot(page, ".strip-right", LABEL + "-strip", "2")
            btn = page.query_selector(".strip-right .chat-settings-btn")
            if btn:
                btn.click(force=True)
                try: page.wait_for_selector("#chat-settings-popup:not(.hidden)", timeout=2000)
                except Exception: pass
                page.wait_for_timeout(300)
                shoot(page, "#chat-settings-popup", LABEL + "-popup", "2", pad=16)
            br.close()
    finally:
        teardown(name)


if __name__ == "__main__":
    sys.exit(main() or 0)
