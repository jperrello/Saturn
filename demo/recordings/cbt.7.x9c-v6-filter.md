# cbt.7 / Saturn-x9c — tighten v6 filter (ULA / 6to4 / Teredo / mixed-case fe80)

**Bead:** Saturn-x9c   **Commit:** `56ee730`

`routable_addrs(family='v6')` previously rejected only `::1`, `::`,
and *exactly-cased* `fe80...`. Three classes of address slipped
through and ended up advertised on the wire:

  - **fe80::/10** — link-local, but mixed-case (`Fe80...`) was passed.
  - **fc00::/7** — Unique Local Addresses (RFC 4193, fc/fd prefixes).
  - **2002::/16** — 6to4 tunneled.
  - **2001::/32** Teredo — matched as `2001::` or `2001:0:` (the
    documentation prefix `2001:db8::/32` is preserved, since it
    starts at the third hextet).

Fix: lowercase the bare address, then reject all four ranges by
prefix. Existing global-unicast addresses still pass.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_v6_filter_gaps_x9c.py
```

The test feeds the filter one address per excluded family plus a
clean global-unicast control; asserts only the control survives.

## Captured output

```text
saturn/tests/test_v6_filter_gaps_x9c.py::
test_v6_filter_excludes_ula_6to4_teredo_mixed_case_fe80 PASSED            [100%]
========================= 1 passed in <Ns> ============================
```

## Why this matters

cbt.7.advertise (`e7b6adf`) packs every routable v6 into the AAAA
record. Without x9c, a Saturn host that happened to have a ULA on its
fc00::/7 fabric would advertise it; peers on the public network would
then dial an unroutable address and silently fail. Same story for
6to4 (deprecated tunnel) and Teredo (NAT-traversal pseudo-addresses).
