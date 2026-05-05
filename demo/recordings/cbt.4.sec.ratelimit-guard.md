# cbt.4.sec.ratelimit — `/api/system/chat` rate-limit regression guard

**Bead:** Saturn-b3o   **Status:** GREEN-on-arrival regression guard
(no implementation commit).

The `_check_rate` infrastructure at `saturn/web.py:293` is already
wired into `brutus_chat` (line 1065) — Phase-3 work pins the invariant
as load-bearing so a future refactor can't silently drop the gate.

## Falsifiable oracle

With `SATURN_RATE_RPM=2`, sending 6 POST requests to `/api/system/chat`
from the same client in rapid succession MUST:

  - yield at least one HTTP **429** (with a `Retry-After` header), AND
  - leave the first 1-2 requests un-429'd (proves the limit is N, not 0).

No mocks — real Saturn web subprocess with the low-rate env, real
loopback client.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_system_chat_ratelimit_b3o.py
```

## Captured output

```text
saturn/tests/test_system_chat_ratelimit_b3o.py::test_burst_triggers_429 PASSED
========================= 1 passed in <Ns> ============================
```

## Why this matters

cbt.4's failover machinery makes `/api/system/chat` the canonical
admin chat surface. Without a pinned rate-limit guard, an
optimisation that re-orders middleware could leave the surface
DDoS-able with a single bearer; b3o makes "rate-limit on this
endpoint" part of the test contract.
