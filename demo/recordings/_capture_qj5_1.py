import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

from tests.harness import ollama, service, web

OUT = pathlib.Path("demo/recordings")
NAME = "qj5-1-capture"
LABEL = os.environ.get("LABEL", "after")


def shoot(origin):
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1440, "height": 900},
                             device_scale_factor=2)
        page = ctx.new_page()
        page.goto(origin)
        page.wait_for_load_state("networkidle")
        tab = page.query_selector('[data-tab="chat"]')
        if tab: tab.click()
        page.wait_for_timeout(400)
        for sel in ('button:has-text("CONTINUE TO CHAT")',
                    'button:has-text("I UNDERSTAND")'):
            btn = page.query_selector(sel)
            if btn:
                btn.click(); page.wait_for_timeout(600); break
        strip = page.query_selector(".chat-topbar")
        if strip:
            box = strip.bounding_box()
            page.screenshot(path=str(OUT / f"qj5.1-top-strip-{LABEL}.png"),
                            clip={"x": 0, "y": max(0, box["y"] - 8),
                                  "width": 1440,
                                  "height": box["height"] + 16})
            print(f"OK strip-{LABEL} box={box}")
        else:
            print(f"WARN: .chat-strip not found, taking full page")
        page.screenshot(path=str(OUT / f"qj5.1-chat-full-{LABEL}.png"))
        br.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ollama.ensure()
    service.install(NAME, priority=40)
    service.start(NAME)
    try:
        with web.serve() as srv:
            shoot(srv["origin"])
    finally:
        service.stop(NAME); service.delete(NAME)


if __name__ == "__main__":
    sys.exit(main() or 0)
