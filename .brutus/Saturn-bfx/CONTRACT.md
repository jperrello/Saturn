# CONTRACT — Saturn-bfx / cbt.8.integrate: advertiser TXT validate + mtrunc

**Status:** RED. 2 tests pinned.
**Implementer:** athena → hardener.

## Spec restatement (falsifiable)

`SaturnAdvertiser._properties()` (`saturn/discovery.py:478-520`) and
`.register()` (line 521-540) MUST integrate the qj5/cbt.8 validator from
`saturn/mdns/txt.py` per §17.G.4.3:

1. **Self-pruning:** when `_properties()` would produce a TXT exceeding
   `TXT_SAFE_CEILING`, prune `models` further → then `capabilities` →
   then `features` until under ceiling. Set `mtrunc="1"` on the result so
   consumers know the payload is partial.

2. **Fail-loud:** if pruning cannot bring the TXT under ceiling (bloat
   lives in unprunable fields like `api_base`), `register()` MUST raise
   `TxtTooLarge`. The current `try/except Exception → return False` swallow
   in `register()` is the symptom.

## Test files

- `saturn/tests/test_advertise_mtrunc_cbt8_integrate.py` (added; 2 tests).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_advertise_mtrunc_cbt8_integrate.py --no-header -rN --tb=short
```

## Captured red

```
test_prune_and_mtrunc_under_capabilities_bloat:
  TxtTooLarge: TXT entry 'capabilities' value is 2712 bytes (>255 RFC 6763 §6.1 cap per entry)
test_register_raises_txt_too_large_on_unprunable_bloat:
  Failed: DID NOT RAISE <class 'saturn.mdns.txt.TxtTooLarge'>
========================= 2 failed, 1 warning in 0.17s =========================
```

Transcript: `.brutus/Saturn-bfx/transcript.md`.

## Oracle

| Test | Oracle |
|---|---|
| prune-and-mark | `validate(props) <= TXT_SAFE_CEILING`; `props["mtrunc"] == "1"` |
| fail-loud | `register()` raises `TxtTooLarge` (no swallow) |

## Fix sketch

In `_properties()` after building `props`, loop:

```python
from saturn.mdns import txt as _txt
def _try_validate(p):
    try: _txt.validate(p); return None
    except _txt.TxtTooLarge as e: return e

while _try_validate(props) is not None:
    if props.get("models"):
        # drop one model
        ms = props["models"].split(",")
        if ms:
            props["models"] = ",".join(ms[:-1])
            props["mtrunc"] = "1"
            continue
    if props.get("capabilities"):
        cs = props["capabilities"].split(",")
        if cs:
            props["capabilities"] = ",".join(cs[:-1])
            props["mtrunc"] = "1"
            continue
    if props.get("features"):
        props["features"] = ""
        props["mtrunc"] = "1"
        continue
    break  # nothing left to prune
```

Then in `register()`, validate one last time and let `TxtTooLarge` propagate
(remove the broad `except Exception`).

## Out of scope

- `SATURN_TXT_CEILING` env override (§17.G.4.5) — file as **bfx.env** if needed.
- CLI surface change for `saturn serve` (§17.G.4.4) — UI/CLI lane.
- Per-backend TXT-size handling differences (Bonjour vs Avahi vs userspace).

## Implementer

athena → hardener. ETA ~15 min.
