import sys

from playwright.sync_api import sync_playwright

from . import ollama, service, web


def main():
    name = "harness-pw-example"
    ollama.ensure()
    service.install(name, priority=40)
    meta = service.start(name)
    try:
        with web.serve() as origin, sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(origin)
            page.wait_for_load_state("networkidle")
            title = page.title()
            chat_tab = page.query_selector('[data-tab="chat"]')
            page.screenshot(path="/tmp/saturn-harness-pw.png", full_page=True)
            print(f"OK: title={title!r} chat_tab={'yes' if chat_tab else 'no'} "
                  f"shot=/tmp/saturn-harness-pw.png")
            browser.close()
    finally:
        service.stop(name); service.delete(name)


if __name__ == "__main__":
    sys.exit(main() or 0)
