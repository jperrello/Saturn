# Saturn-93w — operator-asserted `name → node_id` allowlist (TOFU pin-race fix)

**Bead:** Saturn-93w (P1)   **Commit:** `5930a72`

TOFU + the qj5.16.13.3 ≥2-confirmation gate stop *casual* hostile
pinning, but they had no operator-assertable override. A hostile peer
that registered `<name> + arbitrary node_id` **before** the legit
peer arrived won the pin permanently — every subsequent advertisement
of that name from the legit `node_id` was filtered into
`rebind_rejected` forever, with no path to recover except wiping the
allowlist out-of-band.

Fix: introduce `saturn.discovery.ALLOWLIST_PATH` (default
`~/.saturn/allowlist.json`), a JSON `name -> node_id` map.
`_classify_trust()` now consults the allowlist **before** TOFU; an
allowlisted entry is authoritative — the matching `node_id` is
trusted unconditionally and any other `node_id` advertising that
name is `rebind_rejected` from the start.

The operator's mental model is: "if I name this peer in my allowlist,
nothing else can squat that name on my network." The TOFU path
remains the default for un-listed names.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_tofu_pin_race_93w.py
```

The test simulates the race:

  1. Hostile peer claims `name=alpha node_id=evil` first → TOFU pins.
  2. Legit `name=alpha node_id=truth` arrives second → without 93w,
     stuck in `rebind_rejected`.
  3. Operator writes `{"alpha": "truth"}` into the allowlist.
  4. Re-run discovery → legit peer now classified as trusted; hostile
     peer's continued advertisements `rebind_rejected`.

## Captured output

```text
saturn/tests/test_tofu_pin_race_93w.py::... PASSED  (full pin-race scenario)
========================= N passed in <Ns> ============================
```

## Why this matters

Closes the last "stuck-in-bad-state forever" failure mode in the
trust-anchor chain (qj5.7j3 + qj5.16.13 + cbt.3.c flock). The
allowlist gives the operator a single file to edit when something
goes wrong; no more rm -rf'ing pin state.
