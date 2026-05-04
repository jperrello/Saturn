import pathlib
import sys

from playwright.sync_api import sync_playwright

from tests.harness import ollama, service, web

OUT = pathlib.Path("demo/recordings")
NAME = "qj5-5-capture"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ollama.ensure()
    service.install(NAME, priority=40)
    service.start(NAME)
    try:
        with web.serve() as origin, sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900},
                                 device_scale_factor=2)
            page = ctx.new_page()
            page.goto(origin)
            page.wait_for_load_state("networkidle")
            tab = page.query_selector('[data-tab="chat"]')
            if tab: tab.click()
            page.wait_for_timeout(500)
            # dismiss the experimental-feature gate if present
            for sel in ('button:has-text("CONTINUE TO CHAT")',
                        'button:has-text("I UNDERSTAND")'):
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    page.wait_for_timeout(800)
                    break
            page.screenshot(path=str(OUT / "qj5.5-chat-full.png"), full_page=False)
            area = page.query_selector(".chat-input-area")
            if area:
                area.screenshot(path=str(OUT / "qj5.5-send-aligned.png"))
                box = area.bounding_box()
                page.screenshot(path=str(OUT / "qj5.5-send-region.png"),
                                clip={"x": max(0, box["x"] - 24),
                                      "y": max(0, box["y"] - 24),
                                      "width": box["width"] + 48,
                                      "height": box["height"] + 48})
                print(f"OK send-area box={box}")
            else:
                print("WARN: .chat-input-area not found")
            br.close()
    finally:
        service.stop(NAME); service.delete(NAME)


if __name__ == "__main__":
    sys.exit(main() or 0)
