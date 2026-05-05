# CONTRACT — Saturn-eon / cbt.4.sec.api_base: sanitize ALL TXT values

**Status:** RED. 4/5 tests fail (1 sanity-control passes).
**Implementer:** athena → hardener (P2; defense-in-depth alongside Saturn-xqw).
**Geoff cite:** `FAILOVER_SECURITY.md` §(D).

## Spec restatement (falsifiable)

`saturn/discovery.py:478-483`'s `_sanitize_txt_value` strips `=`, `\x00`,
`\n`, `\r` and caps length, but is applied **only to `models`** in
`_properties()` (line 528). Other emitted TXT values (`api_base`,
`api_type`, `deployment`, `cost`, etc.) pass through unsanitized.

The fix MUST guarantee: every value in the dict returned by
`SaturnAdvertiser._properties()` is free of `\n`, `\r`, `\x00`, and `=`.
Apply `_sanitize_txt_value` to all values before they enter the props
dict (or once at the end, mapped over `.values()`).

This is defense-in-depth atop Saturn-xqw — even with the SSRF gate, an
attacker could otherwise smuggle `\n` into other fields and rely on
permissive parsers downstream.

## Test files

- `saturn/tests/test_txt_sanitize_all_eon.py` (added; 4 hostile fields
  parametrized + 1 safe-content sanity).

## Run command

```
cd /Users/jperr/Documents/Saturn && \
  PATH="/Users/jperr/Documents/Saturn/.venv/bin:$PATH" \
  python -m pytest saturn/tests/test_txt_sanitize_all_eon.py --no-header -rN --tb=short
```

## Captured red

```
4 failed, 1 passed, 1 warning in 0.04s
TXT value for key 'dep' carries '\n': 'network\nrogue=true'. Apply
_sanitize_txt_value to all _properties() outputs, not just `models`.
```

(Same shape across all 4 hostile fields.)
Transcript: `.brutus/Saturn-eon/transcript.md`.

## Oracle definition

For every `(k, v)` in `adv._properties().items()`:

| Disallowed in `v` | Reason |
|---|---|
| `"\n"` | RFC 6763 record-separator collision |
| `"\r"` | same |
| `"\x00"` | C-string truncation foothold |
| `"="` | TXT key=value delimiter collision |

Applies regardless of which input field carried the hostile content.

## Fix sketch

```python
# saturn/discovery.py:_properties()
# After building the props dict:
return {k: _sanitize_txt_value(str(v)) for k, v in props.items()}
```

One-line wrap; preserves model-list-already-sanitized behavior because
double-sanitize is idempotent.

## Out of scope

- The 63-byte cap inside `_sanitize_txt_value` — already enforced; not
  modified here.
- Bonjour-side `_encode_txt` length-asserts (geoff §(D) defense-in-depth
  bonus). File as **Saturn-eon.encode** if desired.
- Re-validating consumed TXT values at resolve time — Saturn-xqw covers
  the api_base resolve-side gate; other fields rarely warrant per-field
  validation.

## Implementer

athena → hardener. P2. ETA ~5 min.

## Transcript

`.brutus/Saturn-eon/transcript.md`
