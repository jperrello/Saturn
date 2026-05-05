# cbt.4.sec.token amend — cap `BrutusChat.messages` at 200

**Bead:** Saturn-zor.amend (geoff P3)   **Commit:** `5eac74a`

Phase-3 follow-up to cbt.4.sec.token. The auth gate stops anonymous
abuse but an *authorised* caller could still pass an unbounded
`messages` list — geoff's review flagged P3 risk that the failover
loop could spend non-trivial CPU validating a 10 000-element payload
before any model rejected it.

Fix: `Field(max_length=200)` on `BrutusChat.messages`. Pydantic
rejects oversized lists at validation time with HTTP 422 *before* the
failover loop runs. Cap chosen at 200 per geoff's 200-500
recommendation; real conversations rarely exceed 100 turns.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_system_chat_auth_zor.py::test_oversized_messages_list_returns_422
```

The test ships a 10 001-element messages list with valid bearer; asserts
HTTP 422 with the Pydantic field-validation error naming the cap.

## Captured output

```text
saturn/tests/test_system_chat_auth_zor.py::
test_oversized_messages_list_returns_422 PASSED                           [100%]
========================= 1 passed in <Ns> ============================
```
