# Saturn-jfs — rate-limit `/api/discover`

**Bead:** Saturn-jfs (P2)   **Commit:** `4330b4d`

`GET /api/discover` ran ~9 s of blocking work per request:

  - `discover()`           — 5 s settle window.
  - `isolation.probe()`    — 4 s round-trip.

…with **no** `_check_rate()` gate. 6 attacker requests forced 54 s of
upstream amplification on the Saturn host; a script could pin the
process sustained.

Fix: handler now mirrors `/api/chat` / `/api/proxy/chat` /
`/api/system/chat` — `_client_ip` resolved at entry, `_check_rate`
called immediately, 429 with `Retry-After` when the bucket is
empty. The 5 s + 4 s blocking work only happens after the gate
admits.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_api_discover_ratelimit_jfs.py
```

The test bursts N requests at `/api/discover` from one client with a
low `SATURN_RATE_RPM`, asserts at least one 429 with `Retry-After`,
and that the first 1-2 stay un-429'd (proves the limit is N, not 0).
Real Saturn web subprocess.

## Captured output

```text
saturn/tests/test_api_discover_ratelimit_jfs.py::
test_api_discover_burst_triggers_429 PASSED                               [100%]
========================= 1 passed in <Ns> ============================
```

## Why this matters

`/api/discover` is the single most expensive read on Saturn web by
an order of magnitude — it's the only handler that does both a
discovery settle window and an isolation probe. b3o pinned the gate
on `/api/system/chat`; jfs closes the matching gap on the discovery
surface.
