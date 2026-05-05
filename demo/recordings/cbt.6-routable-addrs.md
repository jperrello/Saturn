# cbt.6 — `routable_addrs()` helper

**Bead:** Saturn-cbt.6   **Commit:** `f99354d`   **Spec:** §17.G.2

New `saturn/mdns/interfaces.py` exposes `routable_addrs() -> list[str]`
returning every non-loopback, non-link-local IPv4 address on UP
interfaces. Filters via `psutil.net_if_addrs()` cross-checked with
`psutil.net_if_stats()[iface].isup`; rejects `127.x` and `169.254.x`.

`psutil>=5.9.0` formalised as a dependency in `pyproject.toml` (already
required by the cbt.5 isolation probe).

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_routable_addrs_cbt6.py
```

## Captured output

```text
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_returns_list_of_ipv4_strings PASSED
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_excludes_loopback_and_link_local PASSED
saturn/tests/test_routable_addrs_cbt6.py::test_routable_addrs_finds_at_least_one_on_typical_host PASSED
========================= 3 passed in <Ns> ============================
```

## Why this matters

A multi-NIC host (Wi-Fi + Ethernet, or two Wi-Fi via dock) currently
advertises only the address Zeroconf happens to bind first; clients on
the other interface never see it. `routable_addrs()` is the input
helper for the §17.G.2 fix that advertises an A record per interface;
register-time integration tracks under `cbt.6.integrate`.
