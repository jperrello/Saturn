import json
import os
import sys
import tempfile
import urllib.error
import uuid

from playwright.sync_api import sync_playwright

from tests.harness import web
from demo.recordings._capture_admin_lib import OUT, admin_page, try_open_admin

LABEL = os.environ.get("LABEL", "after")
PATHS = ["/admin/configure", "/configure"]


def attest(origin, token, name, nid, host):
    s, _ = web.admin_request(origin, "/api/admin/known-nodes/attest",
                             token, method="POST",
                             body={"service": name, "node_id": nid, "host": host})
    return s


def audit_trust_mode(page):
    return page.evaluate("""
        () => {
          const sel = document.getElementById('ac-trust_mode')
                   || document.querySelector('select[name=trust_mode]')
                   || document.querySelector('select[id*=trust][id*=mode]');
          if (!sel) return null;
          const opts = Array.from(sel.options || []).map(o =>
            ((o.value||'') + '|' + (o.textContent||'')).toLowerCase().trim());
          return opts;
        }
    """)


def audit_picker(page, seed_name, seed_prefix):
    return page.evaluate("""
      ([name, prefix]) => {
        const all = Array.from(document.querySelectorAll('*'))
          .filter(e => e.offsetParent);
        const hits = [];
        for (const el of all) {
          const t = (el.innerText || '');
          if (t.length > 4000) continue;
          if (t.includes(name) && t.includes(prefix)) {
            hits.push({tag: el.tagName.toLowerCase(),
                       cls: el.className, len: t.length});
          }
        }
        return hits.slice(0, 5);
      }
    """, [seed_name, seed_prefix])


def audit_rejections(page):
    return page.evaluate("""
        () => {
          const re = /pending\\s+rejections|rebind\\s+rejected|rejections/i;
          const hits = [];
          for (const el of document.querySelectorAll('section, fieldset, .config-section, .admin-section, [data-admin-group]')) {
            if (!el.offsetParent) continue;
            const t = (el.innerText || '');
            if (re.test(t)) hits.push({head: (el.querySelector('legend,h1,h2,h3,h4')||{}).innerText || '',
                                       text_len: t.length});
          }
          return hits;
        }
    """)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qj5-7j3-") as tmp, \
         web.serve(env_extra={"SATURN_DEV_MODE": "1",
                              "SATURN_DATA_DIR": tmp + "/data",
                              "SATURN_SERVICES_DIR": tmp + "/services"}) as srv, \
         sync_playwright() as p:
        seed_name, seed_id = "rebind-target-1", str(uuid.uuid4())
        seed_prefix = seed_id.replace("-", "")[:8]
        try:
            print(f"seed attest: status={attest(srv['origin'], srv['token'], seed_name, seed_id, '192.168.1.42')}  "
                  f"name={seed_name}  prefix={seed_prefix}")
        except urllib.error.HTTPError as e:
            print(f"seed attest: FAIL {e.code}")

        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1400, "height": 1100},
                             device_scale_factor=2)
        page = admin_page(ctx, srv["token"])
        url = try_open_admin(page, srv["origin"], PATHS, "Configure")
        page.wait_for_timeout(800)

        page.screenshot(path=str(OUT / f"qj5.7j3-{LABEL}-fullpage.png"),
                        full_page=True)

        opts = audit_trust_mode(page)
        if opts is None:
            print("\n(a) trust_mode dropdown: NOT FOUND")
        else:
            present = {k: any(k in o for o in opts) for k in ("tofu", "allowlist", "open")}
            print(f"\n(a) trust_mode dropdown: options={opts}")
            print(f"    [{'X' if all(present.values()) else ' '}] all three modes present "
                  f"(tofu={present['tofu']}, allowlist={present['allowlist']}, open={present['open']})")

        hits = audit_picker(page, seed_name, seed_prefix)
        print(f"\n(b) allowlist picker: regions matching seed_name AND prefix: {len(hits)}")
        for h in hits[:3]: print(f"    - {h}")

        rej = audit_rejections(page)
        print(f"\n(c) pending-rejections region: {len(rej)}")
        for h in rej: print(f"    - {h}")

        # 401 regression guards via direct urllib (no bearer)
        print("\n(d) admin endpoints 401 without bearer:")
        import urllib.request as ur
        for method, path, payload in (
            ("GET",  "/api/admin/known-nodes", None),
            ("POST", "/api/admin/known-nodes/attest",
             {"service": "x", "node_id": str(uuid.uuid4())}),
            ("POST", "/api/admin/known-nodes/forget", {"service": "x"}),
        ):
            req = ur.Request(srv["origin"] + path, method=method,
                             data=json.dumps(payload).encode() if payload else None,
                             headers={"Content-Type": "application/json"} if payload else {})
            try:
                ur.urlopen(req, timeout=5).read()
                print(f"    {method:5s} {path:40s} 200 (REGRESSION — must be 401)")
            except urllib.error.HTTPError as e:
                print(f"    {method:5s} {path:40s} {e.code}")

        br.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
