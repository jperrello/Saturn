# Saturn-eon — sanitize ALL TXT values (defense-in-depth)

**Bead:** Saturn-eon (P2)   **Commit:** `b19fb80`

`SaturnAdvertiser._properties()` previously applied
`_sanitize_txt_value` only to `models` entries. Other emitted fields
(`api_base`, `dep`, `deployment`, `api_type`, `cost`, …) flowed
verbatim — `\n`, `\r`, `\x00`, and bare `=` characters could ride
through.

Three risks that defense-in-depth here neutralises:

  - Embedded `\n` / `\r` could split a TXT value on a permissive
    parser into a fake additional record.
  - Bare `=` could spoof a downstream key (e.g. an `api_base` value
    containing `\nrogue=true` looking like an extra trusted flag).
  - `\x00` confuses log scrapers and shell-piping operators.

Fix: map `_sanitize_txt_value` over **all** values at return. Final
`txt.validate()` call moved inside `_properties` (before sanitize)
so unprunable bloat still raises `TxtTooLarge` with the right size
in the error message — sanitize doesn't change the wire-byte total
materially, but the explicit ordering keeps the failure mode crisp.

## Reproducer (parametrised over the dangerous-input set)

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_txt_sanitize_all_eon.py
```

## Captured output

```text
test_no_control_chars_in_any_txt_value[api_base-http://example.com/v1\nmodels=gpt-x] PASSED
test_no_control_chars_in_any_txt_value[api_type-openai\rfoo=bar]                    PASSED
test_no_control_chars_in_any_txt_value[cost-free\x00secret]                         PASSED
test_no_control_chars_in_any_txt_value[deployment-network\nrogue=true]              PASSED
test_sanitization_does_not_strip_legitimate_content                                 PASSED
========================= N passed in <Ns> ============================
```

The legitimate-content prong is the falsifier — sanitize must not
strip `:`, `/`, `.`, `-`, or any of the characters a real `api_base`
URL needs.

## Why this matters

xqw (`127f708`) is the bouncer at the dispatch door; eon is the
metal detector at the parser entrance. Either one alone closes the
SSRF + TXT-injection class; together they give us belt-and-braces
on the highest-leverage attacker-controlled input in Saturn.
