# cbt.5.1 — `/api/discover` returns `{services, isolation}`

**Bead:** Saturn-5yh   **Commit:** `b6b184f`   **Spec:** §17.G.1.3
**Brutus contract:** `.brutus/Saturn-5yh/CONTRACT.md`

`GET /api/discover` previously returned a bare list of services. cbt.5
(`5c7410c`) shipped the `IsolationProbe` building block but nothing on
the wire surfaced it; the Web-UI couldn't render the AP-isolation
banner without a second round-trip.

Wave-2 wraps the response per §17.G.1.3:

```json
{
  "services": [...],
  "isolation": {
    "advertising": true,
    "self_seen": true,
    "peers_seen": 3,
    "ifaces_with_link": ["en0"],
    "suspected_ap_isolation": false,
    "diagnosis": "healthy"
  }
}
```

Behind the wrapper:

- `saturn.mdns.isolation.probe(timeout=4.0)` is called once per request
  via `loop.run_in_executor` so the FastAPI worker doesn't sit on
  Zeroconf.
- `Web-UI/app.js` bumps to read `body.services`; older builds returning
  a bare list still parse without crashing.
- `window.saturnIsolation` is cached for the §17.G.1.4 UI render bead
  (`cbt.5.1.ui`, bombadil lane). The conditional red-tinted card is
  explicitly **not** in scope here.

## Reproducer (real Zeroconf probe round-trip, no mocks)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_api_discover_isolation_cbt5_1.py
```

## Captured output

```text
saturn/tests/test_api_discover_isolation_cbt5_1.py::
test_api_discover_returns_services_and_isolation PASSED                   [100%]
========================= 1 passed in <Ns> ============================
```

## What still tracks under cbt.5.1.ui

The Web-UI Network Scan tab needs to read `window.saturnIsolation` and
render the yellow / red banner when `suspected_ap_isolation === true`,
with a click-through to manual configuration. Tracks separately —
rodney still pending.
