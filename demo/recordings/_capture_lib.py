import os
import pathlib

from tests.harness import ollama, service, web

OUT = pathlib.Path("demo/recordings")


def boot():
    OUT.mkdir(parents=True, exist_ok=True)
    name = os.environ.get("SVC_NAME", "qj5-cap")
    ollama.ensure()
    service.install(name, priority=40)
    service.start(name)
    return name


def teardown(name):
    service.stop(name)
    service.delete(name)


def open_chat(page, origin):
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


def shoot(page, sel, label, slug, pad=12):
    el = page.query_selector(sel)
    box = el.bounding_box() if el else None
    if not box:
        print(f"WARN qj5.{slug}-{label}: {sel!r} not visible")
        return False
    vw = page.viewport_size["width"]
    vh = page.viewport_size["height"]
    page.screenshot(path=str(OUT / f"qj5.{slug}-{label}.png"),
                    clip={"x": max(0, box["x"] - pad),
                          "y": max(0, box["y"] - pad),
                          "width": min(vw, box["width"] + 2 * pad),
                          "height": min(vh, box["height"] + 2 * pad)})
    print(f"OK qj5.{slug}-{label}: {sel} box={box}")
    return True
