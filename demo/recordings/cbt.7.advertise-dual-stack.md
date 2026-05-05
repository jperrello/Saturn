# cbt.7.advertise — advertise-side dual-stack v4 + v6

**Bead:** Saturn-9rv   **Commit:** `e7b6adf`

Two coordinated changes:

  1. `routable_addrs(family='v4'|'v6'|'both')` extends the cbt.6 helper
     with a family kwarg. `'v4'` stays the default for back-compat with
     every cbt.6 caller (cbt.6.userspace included). `'v6'` returns
     non-link-local non-loopback IPv6; `'both'` interleaves.
  2. `UserspaceBackend.advertise()` packs both families into the
     Zeroconf `ServiceInfo` so the registration carries A and AAAA
     records together.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_dual_stack_advertise_cbt7_advertise.py
```

## Captured output

```text
saturn/tests/test_dual_stack_advertise_cbt7_advertise.py::test_routable_addrs_supports_family_kwarg PASSED
saturn/tests/test_dual_stack_advertise_cbt7_advertise.py::test_userspace_advertise_packs_v4_and_v6_addresses PASSED
========================= 2 passed in <Ns> ============================
```

## Where this fits

cbt.7.advertise is the publish-side counterpart to **cbt.7.resolve**
(`0ccab52`, [`cbt.7.resolve-userspace.md`](cbt.7.resolve-userspace.md)).
With both shipped, a userspace Saturn now both publishes and reads AAAA
records end-to-end.
