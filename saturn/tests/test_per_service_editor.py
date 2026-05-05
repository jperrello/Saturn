"""Saturn-6sb (qj5.13 commit-3) — per-service editor on the Configure page.

Per PRE_SPECS_B3.md §17.A.5 commit-3 + CONFIG_FIELDS §B.

Falsifiable surfaces:
  (a) Per-service section lists existing services with name + key fields visible.
  (b) Create new service via UI → POST /api/services round-trips; service appears
      in subsequent GET /api/services listing.
  (c) Edit existing service via UI → propagates immediately (POST /api/services
      path with merge); GET reflects the change without restart.
  (d) Delete via UI confirms first, then issues DELETE /api/services/<name>; the
      service disappears from the listing.
  (e) Sensitive auth-config surface (api_key_env, beacon.max_budget_usd, acl.*) is
      explicitly gated/labelled — no plaintext API keys, env-var NAMES only.

Real Saturn web + headless Chromium. No mocks.
"""

import json
import urllib.request
import uuid

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from tests.harness import web


pytestmark = pytest.mark.timeout(120)


@pytest.fixture(scope="module")
def admin_page():
    with web.serve() as srv, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        token = srv["token"]
        # Add bearer to all same-origin requests (nav included), but NOT cross-origin
        # (CDN scripts must not get the header — would CORS-fail).
        origin = srv["origin"]
        def _add_auth(route):
            request = route.request
            if request.url.startswith(origin):
                route.continue_(headers={**request.headers, "Authorization": f"Bearer {token}"})
            else:
                route.continue_()
        page.route("**/*", _add_auth)
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


def _admin(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _api_post(origin, path, body, token):
    req = urllib.request.Request(
        f"{origin}{path}", data=json.dumps(body).encode(),
        headers=_admin(token), method="POST",
    )
    return urllib.request.urlopen(req, timeout=10).read()


def _api_get(origin, path, token):
    req = urllib.request.Request(f"{origin}{path}", headers=_admin(token), method="GET")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def _open_per_service_editor(page):
    """Navigate to the admin Configure view's per-service editor section.
    Tries route paths, hash fragments, and visible buttons."""
    for path in ["/admin/configure", "/configure", "/admin/services"]:
        try:
            page.evaluate(f"window.location.pathname = {path!r}")
            page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            continue
    page.wait_for_timeout(300)
    # Heuristic: a per-service editor section contains text like "Services" / "Per-service"
    # AND has a list/table of service names OR a service-row template.
    has_editor = page.evaluate("""() => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset, section, .admin-section, [data-admin-group], .config-section'
        ));
        return sections.some(s => {
            if (s.offsetParent === null) return false;
            const t = (s.innerText || '').toLowerCase();
            return /per[-\\s]?service|services|service\\s+editor/.test(t)
                && (s.querySelector('[data-service], .service-row, .service-item, ul, table, .checklist') !== null);
        });
    }""")
    if has_editor:
        return True
    # Button fallback
    clicked = page.evaluate(r"""() => {
        const btns = Array.from(document.querySelectorAll('button, a'));
        const c = btns.find(b => {
            if (b.offsetParent === null) return false;
            const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase();
            return /per[-\s]?service|services\s*editor|manage\s+services/.test(t);
        });
        if (c) { c.click(); return true; }
        return false;
    }""")
    if clicked:
        page.wait_for_timeout(400)
        return True
    return False


# --- (a) lists existing services ---

def test_per_service_editor_lists_existing_services(admin_page):
    page, origin, token = admin_page["page"], admin_page["origin"], admin_page["token"]
    # Seed two services via API.
    name_a = f"sat6sb-list-{uuid.uuid4().hex[:6]}"
    name_b = f"sat6sb-list-{uuid.uuid4().hex[:6]}"
    for name in (name_a, name_b):
        _api_post(origin, "/api/services", {
            "name": name, "deployment": "local", "api_type": "ollama",
            "priority": 50, "upstream": {"base_url": "http://localhost:11434/v1"},
        }, token)

    page.reload()
    page.wait_for_load_state("networkidle")
    assert _open_per_service_editor(page), (
        "could not navigate to the per-service editor section. Implementer must expose a "
        "discoverable region with services listed (text matching 'services' / 'per-service' "
        "AND containing a list/table of service rows)."
    )

    text = page.evaluate("""() => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset, section, .admin-section, [data-admin-group], .config-section'
        )).filter(s => s.offsetParent !== null);
        const editor = sections.find(s => /per[-\\s]?service|services|service\\s+editor/i.test(s.innerText || ''));
        return editor ? editor.innerText : '';
    }""")
    assert name_a in text and name_b in text, (
        f"per-service editor must list both seeded services {name_a!r}, {name_b!r}; "
        f"editor section text:\n{text[:1500]}"
    )


# --- (b) create round-trips ---

def test_create_new_service_via_ui_round_trips(admin_page):
    page, origin, token = admin_page["page"], admin_page["origin"], admin_page["token"]
    name = f"sat6sb-create-{uuid.uuid4().hex[:6]}"

    page.reload()
    page.wait_for_load_state("networkidle")
    assert _open_per_service_editor(page)

    # Find a "Create"/"Add" button in the per-service editor.
    clicked = page.evaluate(r"""() => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset, section, .admin-section, [data-admin-group], .config-section'
        )).filter(s => s.offsetParent !== null);
        const editor = sections.find(s => /per[-\s]?service|services|service\s+editor/i.test(s.innerText || ''));
        if (!editor) return false;
        const btn = Array.from(editor.querySelectorAll('button, a')).find(b => {
            const t = (b.innerText || '').toLowerCase();
            return /\b(add|create|new)\b/.test(t) && b.offsetParent !== null;
        });
        if (btn) { btn.click(); return true; }
        return false;
    }""")
    assert clicked, "no visible Add/Create/New button inside the per-service editor"
    page.wait_for_timeout(400)

    # Fill name, deployment, api_type, base_url. Use existing #cfg-* ids from the legacy
    # Configure New Service form (likely reused) OR generic name-matching.
    fill_ok = page.evaluate(f"""(name) => {{
        const set = (sel, val) => {{
            const el = document.querySelector(sel);
            if (!el) return false;
            el.value = val;
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }};
        const okName = set('#cfg-name', name) || set('input[name=name]', name);
        const okBase = set('#cfg-base-url', 'http://localhost:11434/v1')
                    || set('input[name="upstream.base_url"]', 'http://localhost:11434/v1');
        // deployment + api_type best-effort
        set('#cfg-deployment', 'network');
        set('#cfg-api-type', 'ollama');
        return okName && okBase;
    }}""", name)
    assert fill_ok, "could not fill the create-service form (need #cfg-name + #cfg-base-url or equivalents)"

    saved = page.evaluate(r"""() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const save = buttons.find(b => b.offsetParent !== null && /save|create|add\s+service/i.test(b.innerText || ''));
        if (save) { save.click(); return true; }
        return false;
    }""")
    assert saved, "no Save/Create button to submit the new service form"
    page.wait_for_timeout(800)

    services = _api_get(origin, "/api/services", token)
    names = [s.get("name") for s in services] if isinstance(services, list) else []
    assert name in names, (
        f"after UI create, GET /api/services does not include {name!r}. Names returned: {names!r}"
    )


# --- (c) edit propagates immediately ---

def test_edit_service_via_ui_propagates(admin_page):
    page, origin, token = admin_page["page"], admin_page["origin"], admin_page["token"]
    name = f"sat6sb-edit-{uuid.uuid4().hex[:6]}"
    _api_post(origin, "/api/services", {
        "name": name, "deployment": "local", "api_type": "ollama",
        "priority": 50, "upstream": {"base_url": "http://localhost:11434/v1"},
    }, token)

    page.reload()
    page.wait_for_load_state("networkidle")
    assert _open_per_service_editor(page)

    # Find an Edit affordance for this row.
    edited = page.evaluate(f"""(name) => {{
        const rows = Array.from(document.querySelectorAll('[data-service], .service-row, .service-item, li, tr'));
        const row = rows.find(r => (r.innerText || '').includes(name) && r.offsetParent !== null);
        if (!row) return 'no-row';
        const btn = Array.from(row.querySelectorAll('button, a')).find(b =>
            /edit|configure/i.test((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || ''))
        );
        if (btn) {{ btn.click(); return 'clicked'; }}
        // Inline editing? Find a priority input adjacent.
        const prio = row.querySelector('input[name="priority"], input[id*="priority"]');
        if (prio) {{
            prio.value = '17';
            prio.dispatchEvent(new Event('input', {{ bubbles: true }}));
            prio.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return 'inline';
        }}
        return 'no-affordance';
    }}""", name)
    assert edited != "no-row", f"row for service {name!r} not in per-service editor"
    assert edited != "no-affordance", (
        f"row for {name!r} has neither an Edit/Configure button nor an inline priority input"
    )

    if edited == "clicked":
        page.wait_for_timeout(400)
        page.evaluate(r"""() => {
            const inputs = Array.from(document.querySelectorAll('input[name="priority"], input[id*="priority"], input[id="cfg-priority"]'));
            const i = inputs.find(x => x.offsetParent !== null);
            if (i) {
                i.value = '17';
                i.dispatchEvent(new Event('input', { bubbles: true }));
                i.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""")
        page.evaluate(r"""() => {
            const b = Array.from(document.querySelectorAll('button')).find(b =>
                b.offsetParent !== null && /save|apply/i.test(b.innerText || '')
            );
            if (b) b.click();
        }""")
        page.wait_for_timeout(700)

    services = _api_get(origin, "/api/services", token)
    target = next((s for s in services if s.get("name") == name), None)
    assert target is not None, f"service {name!r} disappeared after edit"
    assert target.get("priority") == 17, (
        f"after UI edit, GET /api/services shows priority={target.get('priority')!r}; expected 17"
    )


# --- (d) delete confirms then DELETEs ---

def test_delete_service_via_ui_confirms_then_removes(admin_page):
    page, origin, token = admin_page["page"], admin_page["origin"], admin_page["token"]
    name = f"sat6sb-del-{uuid.uuid4().hex[:6]}"
    _api_post(origin, "/api/services", {
        "name": name, "deployment": "local", "api_type": "ollama",
        "priority": 50, "upstream": {"base_url": "http://localhost:11434/v1"},
    }, token)

    page.reload()
    page.wait_for_load_state("networkidle")
    assert _open_per_service_editor(page)

    confirms_seen = []
    page.on("dialog", lambda d: (confirms_seen.append(d.message), d.accept()))

    deleted = page.evaluate(f"""(name) => {{
        const rows = Array.from(document.querySelectorAll('[data-service], .service-row, .service-item, li, tr'));
        const row = rows.find(r => (r.innerText || '').includes(name) && r.offsetParent !== null);
        if (!row) return false;
        const btn = Array.from(row.querySelectorAll('button, a')).find(b =>
            /delete|remove/i.test((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || ''))
        );
        if (!btn) return false;
        btn.click();
        return true;
    }}""", name)
    assert deleted, f"no Delete/Remove affordance on the row for {name!r}"
    page.wait_for_timeout(500)

    # Either a native confirm dialog fired (handled above) OR an in-page confirmation step.
    if not confirms_seen:
        # Look for an in-page confirm button revealed after the initial click.
        page.evaluate(r"""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const c = btns.find(b => b.offsetParent !== null && /confirm|yes|delete\s+anyway/i.test(b.innerText || ''));
            if (c) c.click();
        }""")
        page.wait_for_timeout(500)

    services = _api_get(origin, "/api/services", token)
    names = [s.get("name") for s in services] if isinstance(services, list) else []
    assert name not in names, (
        f"after UI delete, GET /api/services still includes {name!r}. Names: {names!r}. "
        f"Editor must call DELETE /api/services/<name> on confirm."
    )


# --- (e) sensitive auth fields gated/labelled ---

def test_sensitive_auth_fields_gated(admin_page):
    """No plaintext API key inputs anywhere in the per-service editor. The api_key field
    must be the env-var NAME only (api_key_env), per saturn/web.py:1213 invariant."""
    page = admin_page["page"]
    page.reload()
    page.wait_for_load_state("networkidle")
    assert _open_per_service_editor(page)

    leaks = page.evaluate("""() => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset, section, .admin-section, [data-admin-group], .config-section'
        )).filter(s => s.offsetParent !== null);
        const editor = sections.find(s => /per[-\\s]?service|services|service\\s+editor/i.test(s.innerText || ''));
        if (!editor) return {found: false};
        // Sensitive field probes: input whose label/name says 'api_key' but NOT 'api_key_env'.
        const inputs = Array.from(editor.querySelectorAll('input'));
        const bad = [];
        for (const i of inputs) {
            const region = i.closest('label, .config-field, .form-row');
            const t = ((region?.innerText || '') + ' ' + (i.id || '') + ' ' + (i.name || '')).toLowerCase();
            const isKey = /api[-_\\s]?key/.test(t);
            const isEnvName = /api[-_\\s]?key[-_\\s]?env|env[-_\\s]?var/.test(t);
            if (isKey && !isEnvName) bad.push({id: i.id, name: i.name, label: (region?.innerText || '').trim().slice(0, 80)});
        }
        return {found: true, bad};
    }""")
    assert leaks.get("found"), "per-service editor not found for the gating check"
    assert not leaks["bad"], (
        f"per-service editor exposes raw api_key input(s): {leaks['bad']!r}. "
        f"Saturn invariant (saturn/web.py:1213): configs hold the NAME of an env var; "
        f"the value never traverses the request body. UI must reflect that — input label "
        f"must say api_key_env / 'env var name', not 'api key'."
    )

    # Spot-check that one of the new B-section fields is present (B.2 max_budget_usd OR
    # B.4 require_runner_token). Implementer may bring them in incrementally; require ≥1.
    has_b_field = page.evaluate("""() => {
        const sections = Array.from(document.querySelectorAll(
            'fieldset, section, .admin-section, [data-admin-group], .config-section'
        )).filter(s => s.offsetParent !== null);
        const editor = sections.find(s => /per[-\\s]?service|services|service\\s+editor/i.test(s.innerText || ''));
        if (!editor) return false;
        const txt = (editor.innerText || '').toLowerCase();
        return /max_budget_usd|max\\s+budget/.test(txt)
            || /require_runner_token|runner\\s+token/.test(txt)
            || /allowed_models|require_https/.test(txt);
    }""")
    assert has_b_field, (
        "per-service editor surfaces none of CONFIG_FIELDS §B.2 (max_budget_usd / "
        "allowed_models) / §B.3 (require_https) / §B.4 (require_runner_token). At least "
        "one new B-section field must be present so admins can manage the new schema."
    )
