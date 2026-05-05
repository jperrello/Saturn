# cbt.3.a — plumb `settle_time` through `discover()`

**Bead:** Saturn-o6a   **Commit:** `75c58f9`

`SaturnDiscovery.discover(timeout, settle_time)` at
`saturn/discovery.py:278` constructed `SettleDetector()` with no args, so
the hardcoded default in `saturn/mdns/settle.py` always won —
caller-supplied `settle_time` was silently ignored.

Fix: pass `settle_time` through. ~1 line.

## Reproducer (real Zeroconf on 127.0.0.1, no mocks)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_discovery_settle_cbt3a.py
```

The test advertises one real service through a fresh Zeroconf instance,
calls `discover(settle_time=<custom>)` with two distinct settle values,
and asserts the wall-clock duration tracks the requested settle time.
Falsifies the "kwarg ignored" regression directly.

## Captured output

```text
saturn/tests/test_discovery_settle_cbt3a.py::test_settle_time_is_honoured_by_discover PASSED
========================= 1 passed, 1 warning in 5.08s =========================
```

## Why this matters

`settle_time` is the knob that trades discovery latency against
completeness on bursty LANs. cbt.3.b's worker pool gets resolves off the
critical path, but if the settle window itself ignores its kwarg, every
caller is stuck with one default. cbt.3.a is the one-liner that makes
the knob actually work.
