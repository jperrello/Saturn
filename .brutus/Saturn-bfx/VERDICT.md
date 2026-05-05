# VERDICT — Saturn-bfx / cbt.8.integrate

**Status:** GREEN.
**Implementer:** hardener.
**Implementation commit:** `6df7367`.

## Re-run

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_advertise_mtrunc_cbt8_integrate.py \
                   saturn/tests/test_txt_validate_cbt8.py \
                   --no-header -rN --tb=line
========================= 5 passed, 1 warning in 0.08s =========================
```

Both contract tests pass:

- `test_prune_and_mtrunc_under_capabilities_bloat` — `_properties()`
  self-prunes capabilities under bloat; `mtrunc='1'` set; `validate(props)
  ≤ TXT_SAFE_CEILING`.
- `test_register_raises_txt_too_large_on_unprunable_bloat` — `register()`
  raises `TxtTooLarge` on unprunable bloat (no `False` swallow).

Geoff's parity-review wire-in (PARITY_REVIEW_MAY05.md cbt.8.1) is now
load-bearing — the cbt.8 unit tests (`test_txt_validate_cbt8.py`, 3 tests)
remain green, confirming no regression in the validator surface.

Transcript: `.brutus/Saturn-bfx/transcript.md`.
