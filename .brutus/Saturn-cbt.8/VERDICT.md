# VERDICT — Saturn-cbt.8

**Status:** GREEN.
**Implementer:** hardener.

```
saturn/tests/test_txt_validate_cbt8.py — 3 passed
```

`saturn/mdns/txt.py` exposes `TXT_SAFE_CEILING`, `TxtTooLarge(ValueError)`,
and `validate(props) -> int`. Typical 9-key TXT validates under ceiling;
oversized individual entry (300B) and oversized total (~1500B) both raise
with actionable messages. Oracle satisfied.

`SaturnAdvertiser.register()` integration / `mtrunc` truncation remains in
**cbt.8.integrate** sub-bead.

Transcript: `.brutus/Saturn-cbt.8/transcript.md`.
