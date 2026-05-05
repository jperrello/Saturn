# cbt.8 — TXT advertise-time validator

**Bead:** Saturn-cbt.8   **Commit:** `173ad9e`   **Spec:** §17.G.4

New `saturn/mdns/txt.py` exposes:

- `TXT_SAFE_CEILING = 1200` — bytes, well under the typical Ethernet
  fragmentation threshold while leaving headroom for DNS framing.
- `TxtTooLarge(ValueError)` — explicit failure type so callers can
  distinguish "your service config can't be advertised" from generic
  config errors.
- `validate(props: dict) -> int` — returns RFC 6763 §6.1 wire-encoded
  total bytes; raises `TxtTooLarge` when any single `key=value` exceeds
  255 bytes (RFC limit) **or** the running total exceeds the ceiling.

Register-time integration / `mtrunc` graceful-degradation handling is
explicitly out of scope and tracked under `cbt.8.integrate`.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_txt_validate_cbt8.py
```

## Captured output

```text
saturn/tests/test_txt_validate_cbt8.py::test_validate_under_ceiling_returns_total_bytes PASSED
saturn/tests/test_txt_validate_cbt8.py::test_validate_raises_on_oversize_individual_entry PASSED
saturn/tests/test_txt_validate_cbt8.py::test_validate_raises_on_oversize_total PASSED
========================= 3 passed in <Ns> ============================
```

## Why this matters

A TXT record larger than ~1500 bytes risks IP fragmentation or outright
drop on the multicast path. Without advertise-time validation, a
sufficiently chatty `[features]` table silently breaks discovery for
every peer on the network. cbt.8 fails loud at registration instead.
