# cbt.3.c — known-nodes cross-process flock

**Bead:** Saturn-3to   **Commit:** `8d2bbfd`

Two Saturn instances on the same host calling `pin()` /
`record_rejection()` / `attest()` / `forget()` concurrently raced on
the `.tmp -> os.replace` shuffle inside `save()`, producing
`FileNotFoundError` or silently-lost entries. `threading.Lock` only
serialises within a single Python process; a second `saturn web` on the
same data dir blew right past it.

Fix: `fcntl.flock(LOCK_EX)` on a sibling `.lock` file via a `_flock()`
context manager wrapping every mutator. Cross-process serial without
giving up the in-process `threading.Lock`.

## Reproducer (real subprocesses; no mocks)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_known_nodes_cross_proc_cbt3c.py
```

## Captured output

```text
saturn/tests/test_known_nodes_cross_proc_cbt3c.py::
test_concurrent_subprocess_pin_does_not_lose_entries PASSED               [100%]
========================= 1 passed in <Ns> ============================
```

The test fans out `N` subprocesses each calling `pin()` with a unique
node-id, then asserts that every entry survived to the on-disk file.
Falsifies the lost-write race directly.

## Why this matters

The `known-nodes` allowlist is the trust anchor for qj5.7j3 +
qj5.16.13. A silently-lost pin means the next discovery of that node
falls back to TOFU and a freshly-spawned attacker can race to claim
the slot. Cross-process flock closes that window.
