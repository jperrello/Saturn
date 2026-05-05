# cbt.8.integrate — TXT validate + prune + mtrunc + fail-loud at register time

**Bead:** Saturn-bfx   **Commit:** `6df7367`

cbt.8 (`173ad9e`) shipped the `txt.validate()` ceiling check; bfx wires
it into the advertiser path so the ceiling actually gates what hits the
wire.

`SaturnAdvertiser._properties()` now joins `models` + `capabilities`
raw, then enters a prune loop:

  1. If `txt.validate()` is happy, register as-is.
  2. Else pop one `model` and re-validate.
  3. Else pop one `capability` and re-validate.
  4. Else pop `features` whole and re-validate.
  5. Else (still over the ceiling) raise `TxtTooLarge` with a
     human-readable message naming the offending size — register fails
     loud rather than silently truncating into a broken advertisement.

When pruning happens, the dropped fields are recorded under
`mtrunc=<count>` so a peer reading the TXT can tell that the advertiser
had more to say than fit in the wire envelope.

## Reproducer (real `_properties` against a real TXT validator, no mocks)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_advertise_mtrunc_cbt8_integrate.py
```

## Captured output

```text
saturn/tests/test_advertise_mtrunc_cbt8_integrate.py::test_prune_and_mtrunc_under_capabilities_bloat PASSED
saturn/tests/test_advertise_mtrunc_cbt8_integrate.py::test_register_raises_txt_too_large_on_unprunable_bloat PASSED
========================= 2 passed in <Ns> ============================
```

Two prongs:

  - **prune** — a config with bloated `capabilities` lands on a valid
    advertisement with `mtrunc` set; nothing throws.
  - **fail-loud** — a config that can't be pruned under the ceiling
    raises `TxtTooLarge` at register-time with the offending size in
    the message.
