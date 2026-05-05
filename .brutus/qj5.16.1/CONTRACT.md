# CONTRACT: Saturn-qj5.16.1 — runner /v1/* auth + safe bind default

Bead: Saturn-qj5.16.1 (P0, blocks ship)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` F-1 + `CONFIG_FIELDS.md` §A.2 (`runner_token_env`), §A.3 (`bind_host`), §F (invariants).

## Spec restatement
`ServiceRunner.create_app()` must wire a bearer-token dependency on every `/v1/*` route (`/v1/health`, `/v1/models`, `/v1/chat/completions`). The expected token is the value of the env var named by `runner_token_env` (default name `SATURN_RUNNER_TOKEN`, per CONFIG_FIELDS §A.2). Requests without an `Authorization: Bearer <correct>` header must receive HTTP 401; requests with a wrong token must receive 401; requests with the correct token must reach the existing handler (so `/v1/health` returns 200 with `{"saturn": true, ...}`). 401 responses on `/v1/chat/completions` must include `WWW-Authenticate: Bearer` (CONFIG_FIELDS §F). Independently, the default bind host for both `run_service(config, host=...)` and the `saturn-runner` CLI (`main()`'s `--host` argparse default) must flip from `0.0.0.0` to `127.0.0.1`; LAN exposure becomes explicit opt-in (CONFIG_FIELDS §A.3).

Falsifier: any one of the seven assertions below failing means the implementation is wrong.

## Test files
- `saturn/tests/test_runner_auth.py` (new, 7 tests)

## Run command
```
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_runner_auth.py -v
```

## Captured red output
```
============================= test session starts ==============================
collected 7 items

saturn/tests/test_runner_auth.py::test_health_401_without_auth FAILED
saturn/tests/test_runner_auth.py::test_models_401_without_auth FAILED
saturn/tests/test_runner_auth.py::test_chat_completions_401_without_auth FAILED
saturn/tests/test_runner_auth.py::test_health_401_with_wrong_token FAILED
saturn/tests/test_runner_auth.py::test_correct_token_succeeds_and_wrong_token_rejects FAILED
saturn/tests/test_runner_auth.py::test_run_service_default_bind_is_loopback FAILED
saturn/tests/test_runner_auth.py::test_main_argparse_default_host_is_loopback FAILED

E   AssertionError: run_service default host must be 127.0.0.1 (loopback), got '0.0.0.0'
E   assert '0.0.0.0' == '127.0.0.1'

E   AssertionError: main() argparse must default --host to 127.0.0.1; 0.0.0.0 must be explicit opt-in

(401-shape failures: every /v1/* request currently returns 200/503, not 401.)
========================= 7 failed, 1 warning in 0.47s =========================
```

Full re-runnable transcript: `.brutus/qj5.16.1/transcript.md` (showboat).

## Oracle definition
With `SATURN_RUNNER_TOKEN=<token>` set in env, a `ServiceRunner` built from a minimal `ServiceConfig` and exposed via `fastapi.testclient.TestClient` must satisfy all of:

1. `GET /v1/health` with no `Authorization` header → status 401.
2. `GET /v1/models` with no `Authorization` header → status 401.
3. `POST /v1/chat/completions` with no `Authorization` header → status 401, **and** response header `WWW-Authenticate` contains `Bearer` (case-insensitive).
4. `GET /v1/health` with `Authorization: Bearer <wrong>` → status 401.
5. Symmetric: same client, wrong-token request → 401, then correct-token request → 200 with body `{"saturn": true, ...}`.
6. `inspect.signature(saturn.runner.run_service).parameters["host"].default == "127.0.0.1"`.
7. Source of `saturn.runner.main` contains both `"--host"` and `default="127.0.0.1"`.

Token comparison should be constant-time (`hmac.compare_digest` or equivalent) — not directly asserted, but a non-constant-time impl is a finding to surface in review.

## Out of scope (do NOT touch)
- `/api/*` admin routes — that is qj5.16.2.
- TXT-record / beacon `ephemeral_key` exposure — F-2, separate bead.
- Rate limiting (`rate_rpm`/`rate_tpm`) — A.4, separate bead.
- `X-Forwarded-For` trust / `trusted_proxies` — F-3, separate bead.
- TLS (`tls_cert_path`/`tls_key_path`) — F-7, separate bead.
- Web-UI Configure page wiring — qj5.13–15, separate beads.
- Existing tests in `saturn/tests/test_runner.py` must continue to pass; if any break, the auth dependency must be made tolerant of the loopback test client OR the existing tests must add the token header — implementer's call, but the invariant is "no other test regresses."

## Acceptance
1. All 7 tests in `saturn/tests/test_runner_auth.py` go green.
2. `pytest saturn/tests/test_runner.py` continues to pass (no regression in pre-existing runner tests).
3. `WWW-Authenticate: Bearer` present on the chat-completions 401.
4. No tokens written to logs (visual review on green-phase showboat transcript).

## Implementer
hardener

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.1/transcript.md`
