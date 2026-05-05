"""Saturn-eon / cbt.4.sec.api_base — sanitize ALL TXT values, not just models.

Per FAILOVER_SECURITY.md §(D). `_sanitize_txt_value` at
`saturn/discovery.py:478-483` strips `=`, `\\x00`, `\\n`, `\\r` and caps
length, but is applied **only to `models`** (line 528). Other TXT values
(`api_base`, `api_type`, `version`, `deployment`, `features`, `cost`,
etc.) are passed through unsanitized. Combined with the api_base SSRF
gap (Saturn-xqw), an attacker can craft TXT records with embedded
newlines or `=` to potentially confuse downstream parsers.

Falsifiable oracle: when `SaturnAdvertiser._properties()` is called with
control characters embedded in user-controllable fields (`api_base`,
`api_type`, `cost`, `features`, `deployment`, `models`, `capabilities`),
every emitted TXT value MUST have `\\n`, `\\r`, `\\x00`, and `=` stripped.

NO MOCKS. Pure-Python advertiser construction.
"""

import pytest


pytestmark = pytest.mark.timeout(10)


HOSTILE_FIELDS = {
    "api_base":   "http://example.com/v1\nmodels=gpt-x",
    "api_type":   "openai\rfoo=bar",
    "cost":       "free\x00secret",
    "deployment": "network\nrogue=true",
}


def _build_advertiser(**kwargs):
    from saturn.discovery import SaturnAdvertiser
    return SaturnAdvertiser(
        name="eon-test",
        port=9999,
        priority=10,
        models=["legit-model\nrogue=evil"],
        capabilities=["chat\rrogue"],
        context=8192,
        **kwargs,
    )


@pytest.mark.parametrize("field,hostile", list(HOSTILE_FIELDS.items()))
def test_no_control_chars_in_any_txt_value(field, hostile):
    adv = _build_advertiser(**{field: hostile})
    props = adv._properties()
    for k, v in props.items():
        assert "\n" not in v, (
            f"TXT value for key {k!r} carries '\\n': {v!r}. "
            f"Apply _sanitize_txt_value to all _properties() outputs, not just `models`."
        )
        assert "\r" not in v, f"TXT value for {k!r} carries '\\r': {v!r}"
        assert "\x00" not in v, f"TXT value for {k!r} carries NUL: {v!r}"
        assert "=" not in v, (
            f"TXT value for {k!r} carries '=' which collides with the RFC 6763 "
            f"key=value delimiter: {v!r}"
        )


def test_sanitization_does_not_strip_legitimate_content():
    # Sanity: a well-formed advertiser's TXT keys map to non-empty strings.
    adv = _build_advertiser(api_base="https://api.openai.com/v1",
                             api_type="openai",
                             deployment="cloud",
                             cost="paid")
    props = adv._properties()
    assert props.get("api_base") == "https://api.openai.com/v1"
    assert props.get("api_type") == "openai"
    assert props.get("cost") == "paid"
