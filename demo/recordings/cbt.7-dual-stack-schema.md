# cbt.7 — dual-stack address-plural schema

**Bead:** Saturn-cbt.7   **Commit:** `d30e014`   **Spec:** §17.G.3

Schema-only change, by design. Lays the carrier for IPv6 / dual-stack
without disturbing existing callers.

- `ServiceRecord` gains `addresses: list[str]` (A + AAAA, textual;
  default `[]`).
- `SaturnService` gains `addresses: list[str]` (default `[]`) and
  `ipv6: Optional[str]` (first AAAA, default `None`).
- `host` stays as the back-compat primary; existing `service.host`
  callers keep working unchanged.

A-record + AAAA-record advertise wiring, and "prefer IPv6 when both
available" routing, are tracked separately under `cbt.7.advertise` /
`cbt.7.prefer-v6`.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_dual_stack_cbt7.py
```

## Captured output

```text
saturn/tests/test_dual_stack_cbt7.py::test_servicerecord_has_addresses_list_field PASSED
saturn/tests/test_dual_stack_cbt7.py::test_saturnservice_has_addresses_and_ipv6_fields PASSED
saturn/tests/test_dual_stack_cbt7.py::test_servicerecord_addresses_accepts_dual_stack_strings PASSED
========================= 3 passed in <Ns> ============================
```
