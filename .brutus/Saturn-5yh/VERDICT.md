# VERDICT — Saturn-5yh / cbt.5.1

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `b6b184f`.

```
saturn/tests/test_api_discover_isolation_cbt5_1.py — 1 passed
```

`GET /api/discover` now returns `{services: [...], isolation: {...}}`. The
`isolation` dict carries all six `IsolationProbe` fields
(`advertising`, `self_seen`, `peers_seen`, `ifaces_with_link`,
`suspected_ap_isolation`, `diagnosis`). Geoff's PARITY_REVIEW cbt.5.1
wire-in is load-bearing.

Web-UI conditional render of the AP-isolation diagnosis remains in
**cbt.5.1.ui** (bombadil lane). The list-shape consumer at
`Web-UI/app.js:910` should be updated by the implementer or the UI lane.

Transcript: `.brutus/Saturn-5yh/transcript.md`.
