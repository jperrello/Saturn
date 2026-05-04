import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_lib import boot, teardown, shoot, OUT

LABEL = os.environ.get("LABEL", "after")
ADMIN_PW = os.environ.get("SATURN_ADMIN_PASSWORD", "saturn")
PROBE_FIELD = os.environ.get("PROBE_FIELD", "rate_rpm")
PROBE_VALUE_RAW = os.environ.get("PROBE_VALUE", "99")
try: PROBE_VALUE = int(PROBE_VALUE_RAW)
except ValueError: PROBE_VALUE = PROBE_VALUE_RAW


def unlock(page):
    pw = page.query_selector("#admin-pw")
    if not pw: return False
    pw.fill(ADMIN_PW)
    btn = page.query_selector("#admin-pw-submit")
    if btn: btn.click(force=True)
    page.wait_for_timeout(500)
    return page.evaluate("!document.getElementById('admin-section').classList.contains('hidden')")


def capture(page):
    # Network Scan is the default tab; only switch if necessary.
    if not page.query_selector(".tab.active[data-tab='discover']"):
        tab = page.query_selector('[data-tab="discover"]')
        if tab: tab.click(force=True); page.wait_for_timeout(400)
    shoot(page, "#discover", LABEL + "-scan-tab", "13", pad=0)
    if unlock(page):
        shoot(page, "#admin-section", LABEL + "-admin", "13", pad=20)
    page.screenshot(path=str(OUT / f"qj5.13-{LABEL}-fullpage.png"),
                    full_page=True)
    cfg = (page.query_selector("#configure-page")
           or page.query_selector(".configure-page")
           or page.query_selector("#admin-section"))
    if cfg:
        cfg.scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        shoot(page, "#admin-section", LABEL + "-configure", "13", pad=24)


def roundtrip(origin, token):
    s, before = web.admin_request(origin, "/api/admin/config", token)
    try:
        s2, _post = web.admin_request(origin, "/api/admin/config", token,
                                      method="POST",
                                      body={PROBE_FIELD: PROBE_VALUE})
        post_status = s2
    except urllib.error.HTTPError as e:
        post_status = e.code
    s3, after = web.admin_request(origin, "/api/admin/config", token)
    return {"GET_before": before, "POST_status": post_status,
            "GET_after": after,
            "field": PROBE_FIELD, "value": PROBE_VALUE,
            "round_trip_ok": (after or {}).get(PROBE_FIELD) == PROBE_VALUE}


def main():
    import tempfile
    name = boot()
    try:
        with tempfile.TemporaryDirectory(prefix="saturn-qj5-13-") as data_dir, \
             web.serve(env_extra={"SATURN_DEV_MODE": "1",
                                  "SATURN_DATA_DIR": data_dir}) as srv, \
             sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 1100},
                                 device_scale_factor=2)
            page = ctx.new_page()
            page.goto(srv["origin"])
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
            capture(page)
            br.close()
            print(json.dumps(roundtrip(srv["origin"], srv["token"]),
                             default=str, indent=2))
    finally:
        teardown(name)


if __name__ == "__main__":
    sys.exit(main() or 0)
