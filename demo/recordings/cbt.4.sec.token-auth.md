# cbt.4.sec.token — admin gate on `/api/system/chat`

**Bead:** Saturn-zor   **Commit:** `b6ab724`

`/api/system/chat` was the lone `/api/system/*` endpoint without an
auth gate; every other admin-scope surface (status, services,
`tunnel/*`) already required `Depends(require_admin)`. Phase-3
hardening closes the asymmetry: `brutus_chat` now carries the same
dependency.

## Reproducer

```sh
$ "$PY" -m pytest -xvs saturn/tests/test_system_chat_auth_zor.py
```

Three prongs map to the standard 401-401-200 admin-gate matrix:

  1. No `Authorization` header → 401.
  2. Wrong bearer → 401.
  3. Correct bearer → status `!= 401` (the route's own logic continues).

## Captured output

```text
saturn/tests/test_system_chat_auth_zor.py::test_no_auth_returns_401 PASSED
saturn/tests/test_system_chat_auth_zor.py::test_wrong_token_returns_401 PASSED
saturn/tests/test_system_chat_auth_zor.py::test_correct_token_passes_auth PASSED
========================= 3 passed in <Ns> ============================
```

## Test-fixture follow-on

`test_failover_cbt4.py::app_client` predates this gate and was driving
`/api/system/chat` un-bearered. Updated to set `SATURN_ADMIN_TOKEN`
and inject the `Bearer` header on the `TestClient`; all 4 cbt.4
failover tests stay green under the new gate. cbt.4 capture
(`cbt.4-failover.md`) does not need a regenerate — same routing
behaviour, the gate sits *before* the failover machinery and the
test now drives it correctly.
