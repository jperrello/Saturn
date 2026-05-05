# Saturn-828 — Web-UI session-cookie gate (default `Saturn`)

## Contract (per RUN_MAY05_CONTEXT.md)

Whole UI gated behind admin password. Server-verified session cookie.
Default password `Saturn`. First-run + change-password flow.
Hardener landed the gate; bombadil verifies independently in a real
browser against a live `python3 -m saturn web` process.

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | Unauthenticated GET / redirects to /login (303). | `a_unauth_redirect`: status 303, location `/login` |
| b | Wrong password → 401, no `saturn_session` cookie set. | `b_wrong_pw_rejected`: status 401, cookie_set false |
| c | Correct default `Saturn` sets `saturn_session` (HttpOnly) and unlocks /. | `c_cookie_set`: 1 cookie, httpOnly true; `c_redirect_to_login` proves the pre-login bounce |
| d | Logout clears cookie; subsequent / hit redirects to /login. | `d_logout_redirects`: status 303, location `/login` |
| e | First-run: `/api/auth/status` reports `must_change: true`; login.html surfaces the change-password form after default sign-in; new password persists (old default rejected, new unlocks, `must_change` flips false). | `e_first_run_status`, `e_change_form_shown`, `e_change_lands_root`, `e_status_after_change`, `e_old_default_rejected`, `e_new_pw_unlocks` |

## Verification

- Scenario: `tests/bombadil/auth_828.py`
- Run: `python3 tests/bombadil/auth_828.py`
- Result: **PASS** — 11/11 oracle predicates true.
- Artifacts: `tests/bombadil/results/auth_828/result.json`, `after_change.png`.
- Real Web-UI on a live ephemeral port (no MCP, no TestClient).
- Server spawned with `SATURN_ADMIN_CONFIG_PATH` pinned to a tmp file
  so first-run state is guaranteed clean (no leakage from `data/admin_config.json`).
- No mocks. No fixtures. End-to-end: redirect → login form → change-form
  → fresh-context replay of old/new passwords → logout → redirect.

## Independent-verification notes

- `b` covers both 401 status and absence of `saturn_session` in the
  response cookies — guards against a regression where a bogus cookie
  is set before password validation fails.
- `c_cookie_set` asserts `httpOnly: true`; matches `web.py` setting and
  is what stops trivial XSS exfil.
- `e` exercises the **UI** change-form, not just the API: hardener's
  41/41 test_web_session_gate.py is API-level; this scenario proves
  login.html actually wires the must_change branch and the new
  password lands at `/`.

Status: **PASS / independent verification — Saturn-828.**
