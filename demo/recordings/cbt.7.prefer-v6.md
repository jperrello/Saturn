# cbt.7.prefer — `connect_address(service)` + `SATURN_PREFER_V6`

**Bead:** Saturn-76f   **Commit:** `3a2cc30`

New `saturn.discovery.connect_address(service)` returns the address a
client should actually dial:

  - Default — first IPv4 from `service.addresses` (back-compat with
    every existing caller's expectation that "the host is v4").
  - `SATURN_PREFER_V6=1` — first IPv6 if any AAAA was advertised,
    otherwise fall back to v4.

Three falsifiable prongs covered by the test:

  1. Default behaviour returns v4 when both families present.
  2. With `SATURN_PREFER_V6=1` and both families present → v6 wins.
  3. With `SATURN_PREFER_V6=1` and only v4 advertised → v4 (no
     fail-on-missing-v6, no `None` leak).

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_prefer_v6_cbt7_prefer.py
```

## Captured output

```text
saturn/tests/test_prefer_v6_cbt7_prefer.py::test_default_returns_ipv4_when_both_present PASSED
saturn/tests/test_prefer_v6_cbt7_prefer.py::test_prefer_v6_returns_ipv6_when_available PASSED
saturn/tests/test_prefer_v6_cbt7_prefer.py::test_prefer_v6_falls_back_to_v4_when_no_v6 PASSED
========================= 3 passed in <Ns> ============================
```
