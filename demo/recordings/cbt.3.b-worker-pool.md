# cbt.3.b — persistent worker pool for userspace mDNS resolves

**Bead:** Saturn-nu4   **Commit:** `2c9ef90`

`_Listener.add_service` / `update_service` / `remove_service` previously
called `_resolve()` inline on the zeroconf engine thread, serialising
resolves and stacking `get_service_info()` 3-second timeouts under bursty
advertisement (think: 10 services appearing at once → 30-second backlog
before the last one is visible).

Replaced with a `queue.Queue` plus 8 persistent worker threads. Each event
is enqueued with a per-`(action, name)` in-flight dedupe; workers consume
in parallel; the engine thread returns immediately.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_userspace_parallel_resolve_cbt3b.py
```

## Captured output

```text
saturn/tests/test_userspace_parallel_resolve_cbt3b.py::
test_userspace_resolves_run_on_multiple_threads PASSED                    [100%]
========================= 1 passed in <Ns> ============================
```

The test enqueues N concurrent resolves and asserts that more than one
worker thread observed work — falsifies the "all on one thread" regression.

## Why this matters

A burst of mDNS announcements is the normal case at session start
(everyone joins the network within a second of each other). Serialised
resolves made the Network Scan tab look broken for the first ~30 s; the
worker pool makes discovery feel instantaneous on a real LAN.
