# CONTRACT — Saturn-3d9 (cbt.5.1.ui): Web-UI consumes new /api/discover envelope

**Status:** GREEN. The Web-UI patch hardener bundled into commit `b6b184f`
(alongside the Saturn-5yh server change) satisfies cbt.5.1.ui in full —
no follow-up bead needed.

## Spec restatement (falsifiable)

After clicking `#discover-btn` against a saturn web that returns the new
`{services, isolation}` envelope, the Web-UI MUST:

1. Not throw any uncaught JS errors during discovery.
2. Consume `body.services` into the rendered services pipeline
   (proved indirectly via `window.saturnMoons` being an array post-scan
   — `app.js:929` derives it from `discoveredServices` after the
   envelope is unpacked).
3. Cache `body.isolation` to `window.saturnIsolation` as an object
   carrying all six documented fields with the correct primitive types:
   `advertising:bool`, `self_seen:bool`, `peers_seen:number`,
   `ifaces_with_link:array`, `suspected_ap_isolation:bool`,
   `diagnosis:string`.
4. Transition `#scan-status[data-kind]` out of `busy` to one of
   `ok | empty | warn | error` (proves the discover async path actually
   resolved without hanging on the new shape).
5. Backwards-compat: keep both branches alive in source —
   `Array.isArray(body)` (older saturn deployments returning a bare
   list) AND `body.services` (envelope) — so a UI shipped against the
   new server keeps working against an older one. Verified by
   source-level grep on `Web-UI/app.js:912-918`.

## Test file

`tests/bombadil/discover_3d9.py`

## Run command

```
SATURN_PORT=39301 \
  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  tests/bombadil/discover_3d9.py
```

Requires saturn web on `$SATURN_PORT` running code at or after commit
`b6b184f`. The endpoint calls `saturn.mdns.isolation.probe` with a 4s
timeout via `loop.run_in_executor`, so the test budgets ~10s for the
discover round-trip.

## Captured GREEN run (verbatim summary)

```
{
  "post": {
    "moons_is_array": true,
    "isolation_is_object": true,
    "isolation_keys": ["advertising","diagnosis","ifaces_with_link",
                        "peers_seen","self_seen","suspected_ap_isolation"],
    "scan_kind": "empty"
  },
  "fallback_source_check": {
    "envelope_branch_present": true,
    "bare_list_branch_present": true,
    "isolation_cache_present": true
  },
  "js_errors": [],
  "oracle": {
    "no_js_errors": true,
    "services_consumed_via_envelope": true,
    "isolation_object_set": true,
    "isolation_has_documented_fields": true,
    "isolation_field_types": true,
    "scan_status_left_busy": true,
    "fallback_envelope_branch": true,
    "fallback_bare_list_branch": true,
    "fallback_isolation_cache": true
  },
  "pass": true
}
```

Full results: `.brutus/Saturn-3d9/result.json`.

## Why no red phase

This bead exists because Saturn-5yh changed the `/api/discover` response
shape — left unpatched, the Web-UI list-shape would have broken. Hardener
bundled the consumer-side patch into the same commit (`b6b184f`),
collapsing the would-be red into green-on-arrival. Regression-guard
contract per house rules.

## Out of scope (intentionally)

- **Conditional red-tinted card** for `suspected_ap_isolation === true`.
  The 5yh commit message explicitly defers this: *"Conditional red-tinted
  card not in scope here."* Belongs to a separate UI render bead under
  §17.G.1.4 — file when athena is ready.
- **Empty-LAN baseline:** the test runs against a host with no other
  saturn peers (`services` is `[]`, `peers_seen=0`, `diagnosis="loopback
  healthy"`). Multi-peer isolation diagnosis is exercised by the
  saturn-side `test_api_discover_isolation_cbt5_1.py` already shipped
  with 5yh; not re-litigated here.

## Implementer

None. The test IS the attestation.

## Bead

Saturn-3d9 — closes on this attestation.
