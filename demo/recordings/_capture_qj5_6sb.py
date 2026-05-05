import json
import os
import sys
import tempfile
import urllib.error

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_admin_lib import OUT, admin_page, try_open_admin

LABEL = os.environ.get("LABEL", "after")
PATHS = ["/admin/configure", "/admin/services", "/configure", "/admin", "/"]
SEED_NAMES = ["seed-alpha", "seed-bravo"]


def seed(origin, token, name):
    try:
        s, _ = web.admin_request(origin, "/api/services", token, method="POST",
                                 body={"name": name, "deployment": "local",
                                       "api_type": "ollama",
                                       "upstream": {"base_url": "http://localhost:11434/v1"}})
        return s
    except urllib.error.HTTPError as e:
        return e.code


def find_editor(page):
    return page.evaluate("""
        () => {
          const sels = ['fieldset.per-service-editor',
                        '[data-admin-group="services"]',
                        'fieldset', 'section', '.admin-section',
                        '[data-admin-group]', '.config-section'];
          const matches = [];
          const seen = new Set();
          for (const sel of sels) {
            for (const el of document.querySelectorAll(sel)) {
              if (!el.offsetParent || seen.has(el)) continue;
              const t = (el.innerText || '').toLowerCase();
              const html = el.innerHTML.toLowerCase();
              if (/per[- ]service|services?(\\s+editor)?/.test(t)
                  && (/\\b(seed-alpha|seed-bravo)\\b/.test(t)
                      || /per-service-list|per-service-add/.test(html))) {
                seen.add(el);
                matches.push({sel,
                              head: (el.querySelector('legend,h1,h2,h3,h4') || {}).innerText || '',
                              text_len: el.innerText.length,
                              has_seed: /\\b(seed-alpha|seed-bravo)\\b/.test(t)});
              }
            }
          }
          return matches;
        }
    """)


def has_api_key_plaintext(page):
    return page.evaluate("""
        () => {
          const inputs = Array.from(document.querySelectorAll('input'));
          return inputs.filter(i => {
            const k = ((i.id || '') + ' ' + (i.name || '') + ' ' +
                       (i.getAttribute('aria-label') || '')).toLowerCase();
            return /api[-_ ]?key/.test(k) && !/env/.test(k);
          }).map(i => i.outerHTML.slice(0, 120));
        }
    """)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qj5-6sb-") as tmp, \
         web.serve(env_extra={"SATURN_DEV_MODE": "1",
                              "SATURN_DATA_DIR": tmp + "/data",
                              "SATURN_SERVICES_DIR": tmp + "/services"}) as srv, \
         sync_playwright() as p:
        for n in SEED_NAMES:
            print(f"seed {n}: {seed(srv['origin'], srv['token'], n)}")

        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1400, "height": 1000},
                             device_scale_factor=2)
        page = admin_page(ctx, srv["token"])
        url = try_open_admin(page, srv["origin"], PATHS, "Services")
        page.wait_for_timeout(800)
        # Click Add Service to surface the form fields (B-section keywords).
        add = page.query_selector("#per-service-add")
        if add:
            try: add.click(force=True); page.wait_for_timeout(400)
            except Exception: pass
        page.screenshot(path=str(OUT / f"qj5.6sb-{LABEL}-fullpage.png"),
                        full_page=True)

        editors = find_editor(page)
        print(f"resolved url: {url}")
        print(f"per-service editor regions found: {len(editors)}")
        for e in editors: print(f"  - {e}")

        leaks = has_api_key_plaintext(page)
        print(f"plaintext api-key inputs (must be 0): {len(leaks)}")
        for l in leaks: print(f"  LEAK: {l}")

        # Look for B-section fields by id, name, or visible label text.
        haystack = page.evaluate("""
            () => (document.body.innerText + ' ' +
                   Array.from(document.querySelectorAll('input,select'))
                     .map(i => (i.id||'') + ' ' + (i.name||'')).join(' ')).toLowerCase()
        """) or ""
        for kw in ("max_budget_usd", "allowed_models", "require_https",
                   "require_runner_token", "api_key_env"):
            print(f"  [{'X' if kw in haystack else ' '}] surfaces: {kw}")

        try:
            s, after = web.admin_request(srv["origin"], "/api/services",
                                         srv["token"])
            names = [x.get("name") for x in (after or [])]
            print(f"\nGET /api/services: {len(names)} entries; seeded names present: "
                  f"{[n for n in SEED_NAMES if n in names]}")
        except urllib.error.HTTPError as e:
            print(f"\nGET /api/services: {e.code}")

        br.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
