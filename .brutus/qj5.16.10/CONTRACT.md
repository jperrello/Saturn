# CONTRACT: Saturn-qj5.16.10 — /api/usage* admin auth (close user_id query bypass)

Bead: Saturn-qj5.16.10 (P1)
Branch: `autonomous/promo-push`
Spec source: `SECURITY_AUDIT.md` §8.5 + §9.6 + `CONFIG_FIELDS.md` §A.5 (auth matrix entry for `/api/usage*`).

## Spec restatement
`saturn/web.py:1246` (`GET /api/usage`) and `:1275` (`GET /api/usage/history`) currently accept a `user_id` Query parameter that overrides `_client_ip()`. On a /24 LAN any peer iterates 254 IPs and reads each peer's daily token totals + N-day history. Per CONFIG_FIELDS §A.5 both routes belong under `admin_token_env`. Apply `Depends(require_admin_token)` to both. Caller-supplied `user_id` is then intentional admin-only "read any row." `POST /api/usage/report` stays self-report keyed by `_client_ip(request)` only — body must not accept a `user_id` field that re-attributes the write.

Falsifier: any of the six assertions below failing means the implementation is wrong.

## Test files
- `saturn/tests/test_usage_auth.py` (new, 6 tests)

## Run command
```
cd /Users/jperr/Documents/Saturn && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pytest saturn/tests/test_usage_auth.py -v
```

## Captured red output (excerpt — full re-runnable transcript at `.brutus/qj5.16.10/transcript.md`)
```
collected 6 items

6 failed in 0.89s

FAILED test_usage_401_without_auth
FAILED test_usage_history_401_without_auth
FAILED test_usage_401_with_wrong_bearer
FAILED test_usage_admin_can_read_any_row
FAILED test_usage_history_auth_matrix
FAILED test_usage_report_forged_user_id_does_not_attribute
```

## Oracle definition
Fixture: `SATURN_ADMIN_TOKEN`, `SATURN_ADMIN_PASSWORD`, `SATURN_DATA_DIR` set; `saturn.web` reloaded so the env reads at boot. `TestClient` against `web.app`.

1. `GET /api/usage` (with or without `?user_id=<x>`) **without** auth → **401**.
2. `GET /api/usage/history` (with or without `?user_id=<x>&days=N`) **without** auth → **401**.
3. `GET /api/usage` with `Authorization: Bearer <wrong>` → **401**.
4. With admin bearer: `POST /api/usage/report` records caller usage; `GET /api/usage` returns caller row; `GET /api/usage?user_id=<seed_ip>` returns the same row contents (admin-intentional cross-row read).
5. `GET /api/usage/history` auth matrix: no-auth → 401, admin → 200, body is a list.
6. `POST /api/usage/report` with body `{"tokens_in": 7, "tokens_out": 8, "user_id": "10.0.0.99"}` either rejects (422) or accepts-and-ignores (200). A subsequent admin `GET /api/usage?user_id=10.0.0.99` must show `tokens_in == 0` and `tokens_out == 0` (forgery had no effect). The unauth GET on the same path must 401.

## Out of scope (do NOT touch)
- `/api/rate-limit/status` — still public (returns the *caller's* limits keyed by `_client_ip`); keep it that way.
- `POST /api/usage/report` itself stays unauth-callable (legitimate self-report path). Do not require admin auth on the report write — that breaks legitimate clients. The forgery defense is "body has no `user_id` field with effect," not "auth required."
- F-3 trusted_proxies / `X-Forwarded-For` discipline — separate bead. The forgery test does NOT assert XFF behaviour; it only verifies the *body* cannot re-attribute.
- Schema changes to the `usage` table — none required.
- Replacing `"saturn"` default password — F-9, separate bead.
- Other `/api/*` routes — covered by qj5.16.2 (already green at 370f9fa).

## Acceptance
1. All 6 tests in `saturn/tests/test_usage_auth.py` go green.
2. `pytest saturn/tests/test_runner_auth.py saturn/tests/test_web_admin_auth.py` continues to pass — no regression on qj5.16.1 / qj5.16.2.
3. Constant-time bearer comparison reused from qj5.16.2's `require_admin_token` (review item, not asserted).
4. No tokens or per-peer usage rows leaked in error messages — visual on green-phase showboat.

## Implementer
hardener (per athena routing — same pane that landed 16.1 fbb5896 + 16.2 370f9fa)

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.16.10/transcript.md`
