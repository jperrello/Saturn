# cbt.5 — AP-isolation probe

**Bead:** Saturn-cbt.5   **Commit:** `5c7410c`   **Spec:** §17.G.1
**Repro notes:** [`cbt.5_ap_isolation_repro.md`](cbt.5_ap_isolation_repro.md)

New `saturn/mdns/isolation.py` exposes:

- `IsolationProbe` dataclass: `advertising`, `self_seen`, `peers_seen`,
  `ifaces_with_link`, `suspected_ap_isolation`, `diagnosis`.
- `probe(timeout=4.0) -> IsolationProbe` — advertises a transient
  `_saturn-probe._tcp.local.` record on a random loopback port and
  browses for it from the same Zeroconf instance.

Decision matrix:

| advertising | self_seen | suspected_ap_isolation |
|-------------|-----------|------------------------|
| True        | True      | False (healthy)        |
| True        | False     | **True** — multicast escapes the host but doesn't loop back |
| False       | n/a       | False — different failure (no zeroconf engine) |

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_isolation_cbt5.py
```

## Captured output

```text
saturn/tests/test_isolation_cbt5.py::test_isolation_probe_module_surface PASSED
saturn/tests/test_isolation_cbt5.py::test_loopback_probe_self_seen_is_true PASSED
========================= 2 passed in <Ns> ============================
```

The loopback test is the falsifiable one: under healthy conditions on
the dev host, `probe()` MUST set `self_seen=True`. The
`suspected_ap_isolation` branch is exercised against the real
isolated-network reproduction in `cbt.5_ap_isolation_repro.md` (operator-
grade) and via `UserspaceBackend.fault_filter` injection (developer-grade).

## Web-UI integration

Pending — once `/api/system/network/scan` consumes `IsolationProbe` and
the Network Scan tab renders the yellow banner + "switch to manual config"
link, capture a rodney still and replace this section with the screenshot
reference.
