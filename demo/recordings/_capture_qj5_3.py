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
            tools = page.query_selector("#tools-toggle")
            if tools:
                tools.click(); page.wait_for_timeout(400)
            shoot(page, "#tools-panel", LABEL + "-panel", "3")
            shoot(page, "#mcp-servers-config", LABEL + "-mcp", "3")
            br.close()
    finally:
        teardown(name)


if __name__ == "__main__":
    sys.exit(main() or 0)
