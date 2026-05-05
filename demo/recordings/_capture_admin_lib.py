import os
import pathlib

from tests.harness import web

OUT = pathlib.Path("demo/recordings")

INJECT = """
(() => {
  const t = '__SATURN_ADMIN_TOKEN__';
  try { sessionStorage.setItem('saturn-admin-token', t); } catch {}
  try { sessionStorage.setItem('saturn-admin', '1'); } catch {}
  const orig = window.fetch;
  window.fetch = (input, init) => {
    init = init || {};
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.includes('/api/')) {
      init.headers = new Headers(init.headers || {});
      if (!init.headers.has('Authorization')) {
        init.headers.set('Authorization', 'Bearer ' + t);
      }
    }
    return orig(input, init);
  };
})();
"""


def admin_page(ctx, token):
    ctx.set_extra_http_headers({"Authorization": f"Bearer {token}"})
    page = ctx.new_page()
    page.add_init_script(INJECT.replace("__SATURN_ADMIN_TOKEN__", token))
    return page


def try_open_admin(page, origin, paths, button_pattern):
    for p in paths:
        url = origin + p
        try:
            page.goto(url, wait_until="networkidle", timeout=8000)
        except Exception:
            continue
        if page.evaluate(
            "() => document.querySelectorAll('fieldset.config-section, "
            ".admin-section, [data-admin-group]').length"
        ) >= 4:
            return url
    btn = page.query_selector(f"button:has-text('{button_pattern}')")
    if btn:
        try: btn.click(force=True); page.wait_for_timeout(800)
        except Exception: pass
    return None
