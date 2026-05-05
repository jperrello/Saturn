import json
import os
import sys
import tempfile
import urllib.error

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_admin_lib import OUT, admin_page, try_open_admin

LABEL = os.environ.get("LABEL", "after")
PATHS = ["/admin/configure", "/configure", "/admin", "/#admin", "/#configure", "/"]
GROUPS = [
    ("A.1 General",      ["model filter", "budget", "general"]),
    ("A.2 Auth",         ["auth", "token", "session"]),
    ("A.3 Network",      ["network", "bind", "tls", "cors"]),
    ("A.4 Rate",         ["rate", "limit", "throughput"]),
    ("A.5 Endpoint",     ["endpoint", "public", "route"]),
    ("A.6 Proxy",        ["proxy", "redact"]),
    ("A.7 MCP",          ["mcp"]),
    ("A.8 Identity",     ["identity", "trust", "node"]),
]


def section_audit(page):
    return page.evaluate("""
        () => {
          const els = Array.from(document.querySelectorAll(
            'fieldset.config-section, .admin-section, [data-admin-group]'
          )).filter(e => e.offsetParent);
          return els.map(e => {
            const h = e.querySelector('legend, .section-title, h1, h2, h3, h4');
            return { heading: (h && h.innerText || '').trim(), text_len: e.innerText.length };
          });
        }
    """)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qj5-hft-") as tmp, \
         web.serve(env_extra={"SATURN_DEV_MODE": "1",
                              "SATURN_DATA_DIR": tmp + "/data",
                              "SATURN_SERVICES_DIR": tmp + "/services"}) as srv, \
         sync_playwright() as p:
        # Seed a known admin-config value so populate test has a target.
        try:
            web.admin_request(srv["origin"], "/api/admin/config",
                              srv["token"], method="POST",
                              body={"rate_rpm": 137})
        except urllib.error.HTTPError as e:
            print(f"  seed POST failed: {e.code}")

        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1400, "height": 1000},
                             device_scale_factor=2)
        page = admin_page(ctx, srv["token"])
        url = try_open_admin(page, srv["origin"], PATHS, "Configure")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / f"qj5.hft-{LABEL}-fullpage.png"),
                        full_page=True)

        sections = section_audit(page)
        print(f"resolved url: {url}")
        print(f"visible admin sections: {len(sections)}")
        for s in sections:
            print(f"  - heading={s['heading']!r:40s} text_len={s['text_len']}")

        coverage = []
        page_text = (page.evaluate("document.body.innerText") or "").lower()
        for label, kws in GROUPS:
            hit = any(kw in page_text for kw in kws)
            coverage.append((label, hit))
            print(f"  [{ 'X' if hit else ' ' }] {label}  keywords={kws}")

        try:
            s, after = web.admin_request(srv["origin"], "/api/admin/config",
                                         srv["token"])
            print(f"\nGET /api/admin/config (post-seed): rate_rpm={after.get('rate_rpm')}")
        except urllib.error.HTTPError as e:
            print(f"\nGET /api/admin/config: {e.code}")

        # qj5.13.7 regression guard — admin_configure_route MUST require bearer.
        # Bypass the page's Authorization header and hit the route raw.
        import urllib.request as ur
        print("\nno-bearer probes (must all be 401):")
        for path in ("/admin/configure", "/configure", "/api/admin/config"):
            try:
                r = ur.urlopen(srv["origin"] + path, timeout=5)
                code = r.status
                blob = r.read().decode("utf-8", "replace")
                leaks = [k for k in (
                    "trusted_proxies", "cors_origins", "rate_rpm",
                    "rate_tpm", "trusted_node_ids", "admin_token_env",
                    "runner_token_env", "admin_password_env",
                ) if k in blob]
                tag = "LEAK" if leaks else "no-leak"
                print(f"  {path:32s} {code:3d}  {tag}  fields={leaks}")
            except urllib.error.HTTPError as e:
                print(f"  {path:32s} {e.code:3d}  (gated)")

        br.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
