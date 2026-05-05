"""Saturn-hft (qj5.13 commit-2) — Configure page UI render.

Server-side schema + validators + apply_admin_config landed in 8b1e54d (qj5.13 commit-1
/ qj5.14 boot validators). This contract pins the UI render of the 22-field schema lift
across the eight CONFIG_FIELDS §A.1-A.8 group sections.

Falsifiable surfaces:
  (a) Admin Configure view renders 8 group sections (one per CONFIG_FIELDS §A.1-A.8 group).
  (b) Each section populates current AdminConfig values via fetch on mount.
  (c) Edit → Save round-trips: subsequent GET /api/admin/config reflects the change.
  (d) Invalid-field POST surfaces 422 errors[] inline (next to the offending field, not
      a generic toast).
  (e) Per-chat Settings popup from qj5.2 stays separate: server-wide fields like rate_rpm
      MUST NOT appear in the chat-tab Settings popup.

Real Saturn web + headless Chromium via tests.harness.web.serve() + playwright.
No mocks.
"""

import json
import urllib.request

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from tests.harness import web


pytestmark = pytest.mark.timeout(120)


GROUP_KEYWORDS = [
    # One per CONFIG_FIELDS §A.1-A.8 — tolerant matchers so the implementer chooses headings.
    ["model filter", "budget", "general"],          # A.1 existing
    ["auth", "token", "session"],                   # A.2 authentication
    ["network", "bind", "tls", "cors"],             # A.3 network posture
    ["rate", "limit", "throughput"],                # A.4 rate limits
    ["endpoint", "public", "route"],                # A.5 endpoint policy
    ["proxy", "redact"],                            # A.6 proxy hygiene
    ["mcp"],                                        # A.7 MCP
    ["identity", "trust", "node"],                  # A.8 service identity
]


@pytest.fixture(scope="module")
def admin_page():
    with web.serve() as srv, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Inject the admin token into sessionStorage AND set Authorization on every fetch
        # so the Configure page's load can reach /api/admin/config without UI password flow.
        token = srv["token"]
        page.add_init_script(f"""
            sessionStorage.setItem('admin_token', {token!r});
            sessionStorage.setItem('saturn_admin', '1');
            const _origFetch = window.fetch;
            window.fetch = function(url, opts) {{
                opts = opts || {{}};
                opts.headers = opts.headers || {{}};
                if (typeof url === 'string' && url.includes('/api/')) {{
                    opts.headers['Authorization'] = 'Bearer ' + {token!r};
                }}
                return _origFetch(url, opts);
            }};
        """)

        page.goto(srv["origin"])
        page.wait_for_load_state("networkidle")

        yield {"page": page, "origin": srv["origin"], "token": token}
        browser.close()


def _open_admin_configure(page):
    """Navigate to the admin Configure view. Implementer chooses the path —
    a route, a tab, a button. Test tries the obvious ones in order."""
    # Try route paths first
    for path in ["/admin/configure", "/configure", "/#admin", "/#configure"]:
        try:
            page.evaluate(f"window.location.hash = {path.lstrip('/')!r}" if path.startswith("/#") else f"window.location.pathname = {path!r}")
            page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            continue
        if page.evaluate("() => document.querySelectorAll('fieldset.config-section, .admin-section, [data-admin-group]').length") >= 4:
            return True
    # Fallback: click a button that looks like admin/configure
    candidates = page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, a'));
        return btns
          .filter(b => {
              const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('title') || '')).toLowerCase();
              return /admin\\s*config|configure|server\\s*settings|admin\\s*settings/.test(t);
          })
          .map((_, i) => i);
    }""")
    if candidates:
        page.evaluate(f"document.querySelectorAll('button, a')[{candidates[0]}].click()")
        page.wait_for_load_state("networkidle", timeout=2000)
        return True
    return False


# --- (a) 8 group sections render ---

def test_admin_configure_renders_eight_groups(admin_page):
    page = admin_page["page"]
    assert _open_admin_configure(page), (
        "could not navigate to the admin Configure view via /admin/configure, /#admin, "
        "or any visible 'admin config / configure / server settings' button. "
        "Implementer must expose a discoverable entry point."
    )
    page.wait_for_timeout(500)

    found = page.evaluate("""(keywords) => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset.config-section, .admin-section, [data-admin-group]'
        ));
        const visible = sections.filter(s => s.offsetParent !== null);
        const groupHeadings = visible.map(s => {
            const legend = s.querySelector('legend, h2, h3, .section-title, .admin-section-title');
            return ((legend?.innerText || s.innerText.split('\\n')[0] || '')).toLowerCase();
        });
        const matched = keywords.map(words =>
            groupHeadings.findIndex(h => words.some(w => h.includes(w)))
        );
        return {
            total: visible.length,
            headings: groupHeadings,
            matched_per_group: matched,
        };
    }""", GROUP_KEYWORDS)

    missing = [
        i for i, idx in enumerate(found["matched_per_group"]) if idx == -1
    ]
    assert not missing, (
        f"missing CONFIG_FIELDS §A.{[i+1 for i in missing]!r} group(s) on the admin Configure view. "
        f"visible section headings: {found['headings']!r}"
    )
    assert found["total"] >= 8, (
        f"admin Configure view must render ≥ 8 group sections (one per A.1-A.8); "
        f"found {found['total']} visible sections: {found['headings']!r}"
    )


# --- (b) sections populate from /api/admin/config on mount ---

def test_section_values_populate_from_api(admin_page):
    """Seed a known value via API, navigate to Configure, assert the input shows it."""
    origin, token = admin_page["origin"], admin_page["token"]
    body = {"rate_rpm": 137}
    req = urllib.request.Request(
        f"{origin}/api/admin/config",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10).read()

    page = admin_page["page"]
    assert _open_admin_configure(page)
    page.wait_for_timeout(500)

    # Find any input/select whose value is "137" AND whose label/name region mentions rate_rpm.
    found = page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input, select'));
        for (const i of inputs) {
            if (String(i.value || '').trim() === '137') {
                const region = i.closest('label, .config-field, fieldset, .admin-section');
                const t = ((region?.innerText || '') + ' ' + (i.id || '') + ' ' + (i.name || '')).toLowerCase();
                if (/rate.?rpm|rate.?per.?minute|requests.*minute|rpm/.test(t)) {
                    return { id: i.id || null, value: i.value };
                }
            }
        }
        return null;
    }""")
    assert found is not None, (
        "no input on the Configure view shows the seeded rate_rpm=137 value. "
        "Section mount must fetch /api/admin/config and populate inputs from the response."
    )


# --- (c) edit → save round-trips ---

def test_edit_save_roundtrips(admin_page):
    """Type a new rate_rpm value, click save, verify GET /api/admin/config reflects it."""
    page = admin_page["page"]
    origin, token = admin_page["origin"], admin_page["token"]
    assert _open_admin_configure(page)
    page.wait_for_timeout(300)

    target = 271
    set_ok = page.evaluate(f"""(target) => {{
        const inputs = Array.from(document.querySelectorAll('input[type=number], input[type=text], input:not([type])'));
        for (const i of inputs) {{
            const region = i.closest('label, .config-field, fieldset, .admin-section');
            const t = ((region?.innerText || '') + ' ' + (i.id || '') + ' ' + (i.name || '')).toLowerCase();
            if (/rate.?rpm|requests.*minute|rpm/.test(t)) {{
                i.value = String(target);
                i.dispatchEvent(new Event('input', {{ bubbles: true }}));
                i.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
        }}
        return false;
    }}""", target)
    assert set_ok, "could not locate a rate_rpm input on the admin Configure view"

    saved = page.evaluate(r"""() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const save = buttons.find(b => b.offsetParent !== null && /\bsave\b|\bapply\b/i.test(b.innerText || ''));
        if (!save) return false;
        save.click();
        return true;
    }""")
    assert saved, "no visible Save/Apply button on the admin Configure view"
    page.wait_for_timeout(700)

    req = urllib.request.Request(
        f"{origin}/api/admin/config",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    after = json.loads(urllib.request.urlopen(req, timeout=10).read())
    assert after.get("rate_rpm") == target, (
        f"after UI Save, GET /api/admin/config returned rate_rpm={after.get('rate_rpm')!r}, expected {target}. "
        f"UI POST must call /api/admin/config with the merged delta."
    )


# --- (d) invalid POST surfaces 422 inline per group ---

def test_invalid_value_shows_inline_error(admin_page):
    """Type an invalid bind_host (999.999.999.999), Save, assert an inline error message
    near the bind_host input (not a generic toast or empty state)."""
    page = admin_page["page"]
    assert _open_admin_configure(page)
    page.wait_for_timeout(300)

    set_ok = page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input[type=text], input:not([type]), select'));
        for (const i of inputs) {
            const region = i.closest('label, .config-field, fieldset, .admin-section');
            const t = ((region?.innerText || '') + ' ' + (i.id || '') + ' ' + (i.name || '')).toLowerCase();
            if (/bind.?host|bind\\s*ip/.test(t)) {
                if (i.tagName === 'SELECT') {
                    const opt = document.createElement('option');
                    opt.value = '999.999.999.999'; opt.text = '999.999.999.999';
                    opt.selected = true;
                    i.appendChild(opt);
                } else {
                    i.value = '999.999.999.999';
                }
                i.dispatchEvent(new Event('input', { bubbles: true }));
                i.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
        }
        return false;
    }""")
    assert set_ok, "could not locate bind_host input on the admin Configure view"

    page.evaluate(r"""() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const save = buttons.find(b => b.offsetParent !== null && /\bsave\b|\bapply\b/i.test(b.innerText || ''));
        if (save) save.click();
    }""")
    page.wait_for_timeout(800)

    inline = page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll('input, select'));
        for (const i of inputs) {
            const region = i.closest('label, .config-field, fieldset, .admin-section');
            if (!region) continue;
            const t = ((region.innerText || '') + ' ' + (i.id || '') + ' ' + (i.name || '')).toLowerCase();
            if (/bind.?host|bind\\s*ip/.test(t)) {
                const errs = Array.from(region.querySelectorAll(
                    '.error, .field-error, .invalid-feedback, [aria-invalid=true], .config-error, .err'
                )).filter(e => e.offsetParent !== null && (e.innerText || '').trim());
                return errs.length > 0 ? errs.map(e => e.innerText.trim()).join(' | ') : null;
            }
        }
        return null;
    }""")
    assert inline, (
        "after submitting bind_host=999.999.999.999 (server returns 422), no inline error "
        "appears near the bind_host input. Validation feedback must be inline per group, not "
        "a generic toast — the user needs to know which field failed."
    )


# --- (e) per-chat Settings popup remains separate (regression guard from qj5.2) ---

def test_chat_settings_popup_does_not_show_server_wide_fields(admin_page):
    """qj5.2's per-chat Settings popup is for response style / model override / current
    service. It MUST NOT surface server-wide schema fields like rate_rpm or trusted_proxies."""
    page = admin_page["page"]
    page.goto(admin_page["origin"])
    page.wait_for_load_state("networkidle")
    chat_tab = page.query_selector('[data-tab="chat"]')
    if chat_tab:
        chat_tab.click()
        page.wait_for_load_state("networkidle")
    accept = page.query_selector("#chat-accept")
    if accept and accept.is_visible():
        try: accept.click(timeout=3000)
        except Exception: page.evaluate("document.getElementById('chat-accept')?.click()")
        page.wait_for_load_state("networkidle")

    page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('.chat-settings-btn'));
        const vw = window.innerWidth, vh = window.innerHeight;
        const inView = btns.find(b => {
            const r = b.getBoundingClientRect();
            return r.width > 0 && r.left >= 0 && r.top >= 0 && r.right <= vw && r.bottom <= vh;
        });
        if (inView) inView.click();
    }""")
    page.wait_for_timeout(500)

    leak = page.evaluate("""() => {
        const all = Array.from(document.querySelectorAll('*'));
        const popup = all.find(el => {
            if (el.offsetParent === null) {
                const cs = getComputedStyle(el);
                if (cs.position !== 'fixed' || cs.display === 'none') return false;
            }
            const t = (el.innerText || '').toLowerCase();
            return ['default', 'concise', 'detailed', 'code'].every(w => t.includes(w))
                && t.length < 4000;
        });
        if (!popup) return { found_popup: false };
        const txt = (popup.innerText || '').toLowerCase();
        const leaks = ['rate_rpm', 'rate_tpm', 'trusted_proxies', 'cors_origins',
                       'admin_token_env', 'public_routes', 'tls_cert_path', 'mcp_allowed_urls'];
        const seen = leaks.filter(k => txt.includes(k.toLowerCase().replace('_', ' '))
                                    || txt.includes(k.toLowerCase()));
        return { found_popup: true, seen };
    }""")
    assert leak["found_popup"], "qj5.2 popup did not open — chat Settings entry regressed"
    assert not leak["seen"], (
        f"per-chat Settings popup leaks server-wide schema fields: {leak['seen']!r}. "
        f"qj5.2's popup is for response style / model override / current service ONLY."
    )
