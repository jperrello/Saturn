"""Saturn-cbt.8 / §17.G.4 — TXT record advertise-time validation.

Per PRE_SPECS_B3.md §17.G.4. New module `saturn/mdns/txt.py` MUST expose:

  - TXT_SAFE_CEILING: int (default 1200 bytes)
  - class TxtTooLarge(ValueError)
  - def validate(props: dict[str, str]) -> int
        Returns the total RFC 6763 §6.1 wire-encoded byte count.
        Raises TxtTooLarge if total > TXT_SAFE_CEILING OR any individual
        encoded `key=value` pair > 255 bytes.

This contract pins the validator's three discriminating cases. The
register-time integration / mtrunc behavior in `SaturnAdvertiser.register()`
(saturn/discovery.py:513-532) is filed as a separate sub-bead
(cbt.8.integrate); too much surface for one red→green hop.

NO MOCKS. Pure-Python validator over plain dicts.
"""

import pytest


def _txt():
    try:
        return __import__("saturn.mdns.txt", fromlist=["validate", "TxtTooLarge", "TXT_SAFE_CEILING"])
    except ImportError as e:
        pytest.fail(
            "module saturn/mdns/txt.py does not exist. "
            "Create it per PRE_SPECS_B3.md §17.G.4.2 with: "
            "TXT_SAFE_CEILING (int, default 1200), "
            "class TxtTooLarge(ValueError), "
            "def validate(props) -> int. "
            f"Raw import error: {e}"
        )


def test_validate_under_ceiling_returns_total_bytes():
    txt = _txt()
    props = {
        "version": "1.0",
        "deployment": "network",
        "api_type": "openai",
        "priority": "10",
        "models": "llama3.2,mistral,qwen2.5,phi-3,gemma2",
        "capabilities": "chat,code,vision",
        "context": "8192",
        "cost": "free",
        "id": "abcd1234abcd1234",
    }
    n = txt.validate(props)
    assert isinstance(n, int) and n > 0, (
        f"validate() must return a positive int (total wire-encoded bytes); got {n!r}"
    )
    assert n <= txt.TXT_SAFE_CEILING, (
        f"a typical 9-key TXT must validate under TXT_SAFE_CEILING={txt.TXT_SAFE_CEILING}; "
        f"got {n}"
    )


def test_validate_raises_on_oversize_individual_entry():
    txt = _txt()
    props = {
        "version": "1.0",
        "huge": "x" * 300,
    }
    with pytest.raises(txt.TxtTooLarge) as ei:
        txt.validate(props)
    msg = str(ei.value).lower()
    assert "huge" in msg or "255" in msg or "entry" in msg or "value" in msg, (
        f"TxtTooLarge for an oversized individual entry must mention the offending "
        f"key or the 255-byte cap; got {ei.value!r}"
    )


def test_validate_raises_on_oversize_total():
    txt = _txt()
    # 6 entries × ~250 bytes each = ~1500 bytes total → over 1200 ceiling, but
    # each individual entry is under 255 so only the TOTAL trips the check.
    props = {f"k{i}": "x" * 240 for i in range(6)}
    with pytest.raises(txt.TxtTooLarge) as ei:
        txt.validate(props)
    msg = str(ei.value).lower()
    assert "ceiling" in msg or "total" in msg or "1200" in msg or str(txt.TXT_SAFE_CEILING) in msg, (
        f"TxtTooLarge for total-over-ceiling must mention 'ceiling' / 'total' / "
        f"the byte count; got {ei.value!r}"
    )
