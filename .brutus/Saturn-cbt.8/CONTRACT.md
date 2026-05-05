# CONTRACT — Saturn-cbt.8 / §17.G.4: TXT advertise-time validator

**Status:** RED. 3 tests pinned (module does not exist).
**Implementer:** athena will route (recommended: hardener — pure-Python validator, ~30 LOC).

## Spec restatement (falsifiable)

Create `saturn/mdns/txt.py` exposing:

- `TXT_SAFE_CEILING: int = 1200` — module constant.
- `class TxtTooLarge(ValueError)`.
- `def validate(props: dict[str, str]) -> int` — returns the total RFC 6763
  §6.1 wire-encoded byte count. Raises `TxtTooLarge` if:
  - any single `key=value` pair encoding exceeds **255 bytes** (RFC 6763 §6.1
    cap), OR
  - the running total exceeds `TXT_SAFE_CEILING`.

The error message MUST be actionable: it MUST mention the offending key (for
single-entry overflow) or the ceiling / total (for cumulative overflow).

The register-time integration / `mtrunc` truncation behavior in
`SaturnAdvertiser.register()` (§17.G.4.3) is **out of scope** here. File as
**cbt.8.integrate** when txt.py lands.

## Test files

- `saturn/tests/test_txt_validate_cbt8.py` (added; 3 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_txt_validate_cbt8.py --no-header -rN --tb=short
```

No external dependency.

## Captured red output

```
saturn/tests/test_txt_validate_cbt8.py:27: Failed: module saturn/mdns/txt.py
  does not exist. Create it per PRE_SPECS_B3.md §17.G.4.2 with: TXT_SAFE_CEILING
  (int, default 1200), class TxtTooLarge(ValueError), def validate(props) -> int.
  Raw import error: No module named 'saturn.mdns.txt'
========================= 3 failed, 1 warning in 0.03s =========================
```

Full transcript: `.brutus/Saturn-cbt.8/transcript.md`.

## Oracle definition

| Test | Oracle |
|---|---|
| `validate_under_ceiling_returns_total_bytes` | `n = validate(typical_9key_props); 0 < n <= TXT_SAFE_CEILING` |
| `validate_raises_on_oversize_individual_entry` | 300-byte value → `TxtTooLarge` raised; message mentions the key, "255", "entry", or "value" |
| `validate_raises_on_oversize_total` | 6 keys × 240 bytes → `TxtTooLarge` raised; message mentions "ceiling", "total", "1200", or `TXT_SAFE_CEILING` |

## Fix sketch (non-binding)

```python
# saturn/mdns/txt.py
TXT_SAFE_CEILING = 1200

class TxtTooLarge(ValueError):
    pass

def validate(props):
    total = 0
    for k, v in props.items():
        entry = f"{k}={v}".encode("utf-8")
        # RFC 6763 §6.1: each entry has 1-byte length prefix; max 255 total
        if len(entry) > 255:
            raise TxtTooLarge(
                f"TXT entry '{k}' is {len(entry)} bytes (>255 RFC 6763 cap)"
            )
        total += 1 + len(entry)
        if total > TXT_SAFE_CEILING:
            raise TxtTooLarge(
                f"TXT total {total} exceeds ceiling {TXT_SAFE_CEILING}"
            )
    return total
```

Implementer is free to deviate; oracle is what matters.

## Out of scope

- `SaturnAdvertiser.register()` integration / `mtrunc` flag handling
  (§17.G.4.3 step 2-3) — file as **cbt.8.integrate**.
- `SATURN_TXT_CEILING` env override (§17.G.4.5) — file as **cbt.8.env** if
  desired.
- CLI / Web-UI surfacing of `TxtTooLarge` (§17.G.4.4) — UI lane.

## Implementer

athena will route. Suggested: **hardener**. ETA: ~10 min.

## Transcript

`.brutus/Saturn-cbt.8/transcript.md`
