# CONTRACT: Saturn-qj5.16.2 — saturn/web.py admin endpoints server-side auth

Bead: Saturn-qj5.16.2 (P0, blocks ship)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` F-4 + `CONFIG_FIELDS.md` §A.2 (`admin_token_env`), §A.5 (auth matrix).

## Spec restatement
The FastAPI app in `saturn/web.py` currently has zero server-side auth dependencies; the admin gate at `Web-UI/app.js:1021-1049` is sessionStorage-only theatre. Every `/api/{services,admin,system,mcp}/*` route must enforce server-side bearer-token auth via `Depends(require_admin_token)` resolved against the env var named by `admin_token_env` (default `SATURN_ADMIN_TOKEN`). An equivalent admin session cookie issued by `POST /api/admin/auth` is also acceptable. Forged client-side cookies (`admin_session=...`, `isAdmin=1`) and forged headers (`X-Admin: true`) MUST NOT pass the server check. The only routes that remain public per CONFIG_FIELDS §A.5 default `public_routes`: `POST /api/admin/auth` (issues the credential), `GET /api/discover`, `GET /v1/health`, and the static `/{path:path}` mount.

Falsifier: any of the protected routes returning 200/500 on an unauthenticated request, OR any forged client-side credential producing a non-401, OR any public route 401-ing on an unauthenticated request, falsifies the implementation.

## Test files
- `saturn/tests/test_web_admin_auth.py` (new, 32 tests — 13 routes × 2 negative states + 1 matrix + 2 forged-credential + 3 public-invariant)

## Run command
```
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_web_admin_auth.py -v
```

## Captured red output (excerpt — full re-runnable transcript at `.brutus/qj5.16.2/transcript.md`)
```
collected 32 items

29 failed, 3 passed in 22.54s

Failures cover:
  - 13× test_protected_route_401_without_auth     [parametrized over PROTECTED_ROUTES]
  - 13× test_protected_route_401_with_wrong_bearer [parametrized]
  - 1×  test_admin_config_auth_matrix             (no-auth currently returns 200 — config leak)
  - 1×  test_forged_session_cookie_does_not_bypass (cookies forged → 200, must be 401)
  - 1×  test_forged_header_does_not_bypass        (X-Admin header forged → 200, must be 401)

Passing (correctly, public-route invariants — must remain green post-fix):
  - test_public_admin_auth_accepts_request_shape   (/api/admin/auth wrong-pw → 401 from password check)
  - test_public_admin_auth_succeeds_with_correct_password (correct pw → 200)
  - test_discover_public                          (GET /api/discover reachable unauth)
```

## Oracle definition
Fixture: `SATURN_ADMIN_TOKEN=<token>`, `SATURN_ADMIN_PASSWORD=brutus-fixture-pw-min-12chars`, `SATURN_DATA_DIR=<tmp>` set before importing `saturn.web` (the test reloads the module so the env reads at boot).

For each `(method, path, body)` in `PROTECTED_ROUTES` (the 13 routes listed in the test file: `/api/services`, `/api/services/<n>` CRUD/start/stop, `/api/admin/config` GET+POST, `/api/system/tunnel/start`, `/api/system/tunnel/stop`, `/api/system/status`, `/api/mcp/servers` GET/POST, `/api/mcp/servers/<n>` DELETE):

1. Without `Authorization` header → status **401**.
2. With `Authorization: Bearer <wrong>` → status **401**.

Single-route auth matrix (`/api/admin/config`):

3. No auth → 401, wrong bearer → 401, correct bearer → 200.

Forgery resistance:

4. `GET /api/admin/config` with cookies `{admin_session=forged, saturn_admin=true, isAdmin=1}` → 401.
5. `GET /api/admin/config` with headers `{X-Admin: true, X-Saturn-Admin: 1}` → 401.

Public-route invariants (must remain reachable without auth):

6. `POST /api/admin/auth` with wrong password → 401 (from password check, not from blanket auth dep). Body contains "password" or "invalid password".
7. `POST /api/admin/auth` with correct password → 200.
8. `GET /api/discover` → not 401.

## Out of scope (do NOT touch)
- `/v1/*` runner-side auth — already landed in qj5.16.1 (fbb5896).
- `/v1/*` on the saturn-web side — separate concern, can be picked up after this lands.
- `/api/chat`, `/api/proxy/chat`, `/api/proxy/models`, `/api/models` — these take a **runner-token** per A.5, not the admin token; do not protect them with `require_admin_token` or this contract's tests will break in the wrong direction. They can be left as-is for this bead.
- Replacing the `"saturn"` default password (F-9) — that is a separate validator bead.
- Signed-cookie session machinery for `/api/admin/auth` — the contract accepts ANY mechanism that lets the correct-password flow eventually authenticate subsequent requests, but for the test the bearer-token path is sufficient.
- `X-Forwarded-For` trust / `trusted_proxies` (F-3) — separate bead.
- Static route `/{path:path}` and the Web-UI assets — must remain unauth-reachable; the test does not assert this directly, do not break it.

## Acceptance
1. All 32 tests in `saturn/tests/test_web_admin_auth.py` go green.
2. `pytest saturn/tests/test_runner_auth.py` (qj5.16.1) continues to pass — no regression on the runner side.
3. Existing tests under `saturn/tests/` that exercise `saturn/web.py` keep passing OR are updated to attach the admin token; do not silently delete coverage.
4. Token comparison constant-time (`hmac.compare_digest`) — review item, not directly asserted.
5. No tokens written to logs/responses — visual review on green-phase showboat transcript.

## Implementer
hardener (per athena routing — overseer confirmed implementer is idle awaiting this contract)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.2/transcript.md`
