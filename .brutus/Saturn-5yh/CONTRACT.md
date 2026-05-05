# CONTRACT — Saturn-5yh / cbt.5.1: wire `isolation.probe()` into `/api/discover`

**Status:** RED. 1 test pinned.
**Implementer:** athena → hardener.
**Geoff cite:** `PARITY_REVIEW_MAY05.md` §(c) NEW Saturn-cbt.5.1.

## Spec restatement (falsifiable)

`saturn/web.py:614-633` `GET /api/discover` currently returns a bare list.
Per §17.G.1.3, the response shape MUST become:

```json
{
  "services": [ ... existing per-service entries ... ],
  "isolation": {
    "advertising": <bool>,
    "self_seen": <bool>,
    "peers_seen": <int>,
    "ifaces_with_link": [<string>, ...],
    "suspected_ap_isolation": <bool>,
    "diagnosis": <string>
  }
}
```

Implementation MUST call `saturn.mdns.isolation.probe(timeout=4.0)` once
per request (or cache for ≤30s) and emit the result under `isolation`.

## Test files

- `saturn/tests/test_api_discover_isolation_cbt5_1.py` (added; 1 test).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_api_discover_isolation_cbt5_1.py --no-header -rN --tb=short
```

## Captured red

```
1 failed, 1 warning in 8.42s
GET /api/discover must return a JSON object with `services` and `isolation`
keys per §17.G.1.3; got top-level type list
```

Transcript: `.brutus/Saturn-5yh/transcript.md`.

## Oracle

| Field | Oracle |
|---|---|
| Top-level type | `dict` |
| `body["services"]` | `list` (previous response, nested) |
| `body["isolation"]` | `dict` carrying all 6 IsolationProbe fields |
| `body["isolation"]["diagnosis"]` | `str` |

## Breaking change — Web-UI follow-up

`Web-UI/app.js:910-912` does `discoveredServices = await res.json()` and
iterates as a list. The new shape WILL break this consumer. Implementer
MUST also update Web-UI/app.js to read `body.services` from the wrapped
dict, and (per §17.G.1.4) conditionally render the AP-isolation diagnosis
at line 946.

The Web-UI render assertion (showing the red-tinted card with manual-config
CTA) is NOT covered by this Python contract — file as **cbt.5.1.ui**
(bombadil lane). The implementer should at minimum stop the Web-UI from
crashing on the new shape, even if the AP-isolation render is deferred.

## Out of scope

- Web-UI conditional render of AP-isolation diagnosis → **cbt.5.1.ui**
  (bombadil).
- Caching strategy for the probe (per-request vs 30s cache).
- Probe failure / timeout fallback diagnosis text — fold into existing
  cbt.5.adversarial sub-bead.

## Implementer

athena → hardener. ETA ~15 min (handler change + Web-UI list-access patch).
