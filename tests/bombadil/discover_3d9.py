"""
Saturn-3d9 (cbt.5.1.ui) — Web-UI consumes new /api/discover envelope.

Verifies the Web-UI/app.js patch landed in commit b6b184f handles the new
`/api/discover` response shape `{services, isolation}` per Saturn-5yh:

  1. Triggering the Discover button against a real saturn web on
     $SATURN_PORT must NOT throw and must leave the rendered services
     list in a sane state (no JS errors, the discover-status text
     transitions out of "busy").

  2. After discovery completes, `discoveredServices` (assigned from
     `body.services`) must be an array.

  3. After discovery completes, `window.saturnIsolation` must be a
     populated object carrying the documented isolation fields:
     advertising (bool), self_seen (bool), peers_seen (number),
     ifaces_with_link (array), suspected_ap_isolation (bool),
     diagnosis (string).

  4. Backwards-compat fallback (bare-list shape from older saturn
     deployments) is verified by direct code-reading at
     Web-UI/app.js:912-918: `if (Array.isArray(body))` → assigns array
     to discoveredServices and sets isolation=null. Cannot exercise via
     live backend because current saturn always returns the envelope;
     the fallback branch is gated on actual UI codepath staying in
     place. Asserted by reading the source file at run time and
     confirming both branches are present.

UI-only. Real saturn web. Real /api/discover round-trip (which calls
saturn.mdns.isolation.probe with a 4s timeout — the test budget
accounts for this).
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

from helpers import ORIGIN, results_dir, finalize

OUT = results_dir("discover_3d9")
APP_JS = Path(__file__).resolve().parent.parent.parent / "Web-UI" / "app.js"


def main():
    js_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        page.on("pageerror", lambda exc: js_errors.append(str(exc)))

        # baseline: discover tab is the default landing
        page.goto(ORIGIN, wait_until="domcontentloaded")
        page.wait_for_selector("#discover-btn", timeout=10_000)

        # before we click, isolation should be unset and services-list empty
        pre = page.evaluate("""
            () => ({
                isolation: typeof window.saturnIsolation,
                services_dom_count: document.querySelectorAll('#services-list > *').length,
            })
        """)

        page.click("#discover-btn")
        # wait for the busy state to clear (ok / empty / warn / error)
        page.wait_for_function(
            "() => { const s=document.getElementById('scan-status'); "
            "return s && s.dataset.kind && s.dataset.kind !== 'busy'; }",
            timeout=20_000,
        )

        post = page.evaluate("""
            () => {
                const iso = window.saturnIsolation;
                const moons = window.saturnMoons;
                return {
                    moons_is_array: Array.isArray(moons),
                    services_dom_count: document.querySelectorAll('#services-list > *').length,
                    isolation_is_object: !!iso && typeof iso === 'object',
                    isolation_keys: iso ? Object.keys(iso).sort() : [],
                    isolation_advertising_is_bool: iso && typeof iso.advertising === 'boolean',
                    isolation_self_seen_is_bool: iso && typeof iso.self_seen === 'boolean',
                    isolation_peers_seen_is_number: iso && typeof iso.peers_seen === 'number',
                    isolation_ifaces_is_array: iso && Array.isArray(iso.ifaces_with_link),
                    isolation_suspected_is_bool: iso && typeof iso.suspected_ap_isolation === 'boolean',
                    isolation_diagnosis_is_string: iso && typeof iso.diagnosis === 'string',
                    scan_kind: document.getElementById('scan-status').dataset.kind,
                    scan_text: document.getElementById('scan-status').textContent,
                };
            }
        """)

        page.screenshot(path=str(OUT / "final.png"), full_page=True)
        browser.close()

    # backwards-compat fallback: source-level assertion
    src = APP_JS.read_text()
    fallback = {
        "envelope_branch_present": "body.services" in src,
        "bare_list_branch_present": "Array.isArray(body)" in src,
        "isolation_cache_present": "window.saturnIsolation" in src,
    }

    expected_iso_keys = {"advertising", "diagnosis", "ifaces_with_link",
                          "peers_seen", "self_seen", "suspected_ap_isolation"}

    oracle = {
        "no_js_errors": len(js_errors) == 0,
        "services_consumed_via_envelope": post["moons_is_array"],
        "isolation_object_set": post["isolation_is_object"],
        "isolation_has_documented_fields": expected_iso_keys.issubset(set(post["isolation_keys"])),
        "isolation_field_types": all([
            post["isolation_advertising_is_bool"],
            post["isolation_self_seen_is_bool"],
            post["isolation_peers_seen_is_number"],
            post["isolation_ifaces_is_array"],
            post["isolation_suspected_is_bool"],
            post["isolation_diagnosis_is_string"],
        ]),
        "scan_status_left_busy": post["scan_kind"] in ("ok", "empty", "warn", "error"),
        "fallback_envelope_branch": fallback["envelope_branch_present"],
        "fallback_bare_list_branch": fallback["bare_list_branch_present"],
        "fallback_isolation_cache": fallback["isolation_cache_present"],
    }

    out = {
        "pre": pre,
        "post": post,
        "fallback_source_check": fallback,
        "js_errors": js_errors,
        "oracle": oracle,
        "pass": all(oracle.values()),
    }
    finalize(out, None, OUT)


if __name__ == "__main__":
    main()
