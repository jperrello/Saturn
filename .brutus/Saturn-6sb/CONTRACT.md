# CONTRACT: Saturn-6sb — qj5.13 commit-3: per-service editor on the Configure page

Bead: Saturn-6sb (P1, qj5.13 commit-3)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-6sb` + `PRE_SPECS_B3.md` §17.A.5 commit-3 + `CONFIG_FIELDS.md` §B.

## Spec restatement
Server-side schema lift + admin Configure UI shipped in qj5.13 commit-1 (`8b1e54d`) and Saturn-hft (commit-2, in flight). This contract pins the **per-service editor** that surfaces CONFIG_FIELDS §B fields against the existing `/api/services` CRUD. The editor lives on the admin Configure view as one of the eight group sections (or as a sibling of them — implementer's call), and supports list / create / edit / delete with apply_admin_config-style live propagation.

Five falsifiable surfaces, mapped to the user's spec letters:

- **(a)** Per-service section visibly lists existing services; the section heading mentions `services` / `per-service`, and the rendered text contains each service's name.
- **(b)** UI Create: filling name + base_url + clicking save produces a `POST /api/services` round-trip; the new name appears in `GET /api/services`.
- **(c)** UI Edit: changing a service field (e.g., `priority=17`) and saving propagates immediately; subsequent `GET /api/services` shows the new value without restart.
- **(d)** UI Delete: clicking Delete on a row triggers a confirmation (native `confirm()` dialog OR an in-page Confirm/Yes button), then `DELETE /api/services/<name>`; the service disappears from the listing.
- **(e)** Sensitive auth surface gated: no `api_key` plaintext input may exist in the editor — Saturn's invariant (`saturn/web.py:1213`) is "configs hold the NAME of an env var; the value never traverses the request body." The UI must reflect that — input label says `api_key_env` / "env var name", not "api key". And at least one CONFIG_FIELDS §B.2/B.3/B.4 field (`max_budget_usd` / `allowed_models` / `require_https` / `require_runner_token`) is present.

Falsifier: any of the five tests below failing means the editor is incomplete or the secret-handling invariant has regressed.

## Test files
- `saturn/tests/test_per_service_editor.py` (new, 5 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium 1400×900; admin token injected into `sessionStorage` and as `Authorization: Bearer` on every `/api/*` fetch)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_per_service_editor.py --timeout=90
```

## Captured red output (full transcript at `.brutus/Saturn-6sb/transcript.md`)
```
collected 5 items

5 failed in 71.50s

FAILED test_per_service_editor_lists_existing_services
       — _open_per_service_editor() finds no admin section whose heading mentions
         per-service AND contains a list/table of services.

FAILED test_create_new_service_via_ui_round_trips
       — same root: no editor region resolved.

FAILED test_edit_service_via_ui_propagates
       — same root: no editor region resolved.

FAILED test_delete_service_via_ui_confirms_then_removes
       — same root: no editor region resolved.

FAILED test_sensitive_auth_fields_gated
       — same root: no editor region resolved (the api-key-naming invariant cannot
         be checked until the editor exists).
```

## Oracle definition

Module-scoped fixture: `tests.harness.web.serve()` spawns real `python3 -m saturn web` with admin auth seeded; headless Chromium 1400×900; `add_init_script` injects the admin token into `sessionStorage` AND patches `window.fetch` to add `Authorization: Bearer <token>` on every `/api/*` call.

`_open_per_service_editor(page)` resolves the editor by:
1. Trying `/admin/configure`, `/configure`, `/admin/services` paths.
2. Looking for any visible `fieldset, section, .admin-section, [data-admin-group], .config-section` whose `innerText` matches `per-service | services | service editor` AND contains a list/table/checklist of service rows (`[data-service]`, `.service-row`, `.service-item`, `ul`, `table`, `.checklist`).
3. If neither succeeds, clicking a button whose text/aria matches `per-service | services editor | manage services`.

### (a) `test_per_service_editor_lists_existing_services`
Seed two services via API. Reload + open editor. The editor section's `innerText` must contain both seeded names.

### (b) `test_create_new_service_via_ui_round_trips`
Open editor. Click an `Add | Create | New` button inside the editor. Fill name (`#cfg-name` or `input[name=name]`) + base_url (`#cfg-base-url` or `input[name="upstream.base_url"]`). Best-effort fill `#cfg-deployment` + `#cfg-api-type`. Click `Save | Create | Add Service`. `GET /api/services` returns a list including the new name.

### (c) `test_edit_service_via_ui_propagates`
Seed a service. Open editor. Find its row. Either click an `Edit | Configure` button, or set an inline `priority=17`. Click Save (if needed). `GET /api/services` returns the service with `priority == 17`.

### (d) `test_delete_service_via_ui_confirms_then_removes`
Seed a service. Open editor. Click Delete on its row. Either a native `confirm()` dialog fires (auto-accepted by the test) OR an in-page `Confirm | Yes | Delete anyway` button surfaces and is clicked. `GET /api/services` no longer returns the name.

### (e) `test_sensitive_auth_fields_gated`
Open editor. Within its region, every `<input>` whose label/id/name matches `api[-_ ]?key` MUST also match `api[-_ ]?key[-_ ]?env | env[-_ ]?var` — no plaintext key inputs. Additionally, the editor's text must surface at least one of: `max_budget_usd`, `allowed_models`, `require_https`, `require_runner_token` (CONFIG_FIELDS §B.2/B.3/B.4).

## Out of scope (do NOT touch / explicitly NOT asserted)
- The exact navigation path / heading text / row markup. Anything `_open_per_service_editor` resolves and any of the matched selectors satisfy.
- The full per-service field set. (e) requires only ONE new B-section field to surface — implementer can incrementally land more.
- Confirmation UX shape (native dialog vs. modal vs. inline button). Both shapes satisfy (d).
- Server-side `/api/services` validators for B.3 (`require_https`) / B.4 (`require_runner_token`) / B.2 (`max_budget_usd` mandatory when beacon enabled). Those are separate beads or part of qj5.16.4 / future commits.
- Inline error rendering for invalid edits — Saturn-hft's spec letter (d) covered this for admin server-wide fields; per-service inline errors can mirror that pattern.
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.
- qj5.16.13.* (TrustRebindError, reclassify_all, pin-before-settle) — separate beads.
- Saturn-hft (qj5.13 commit-2 admin server-wide UI) — sibling, must continue to pass.

## Acceptance
1. All 5 tests in `saturn/tests/test_per_service_editor.py` go green.
2. `pytest saturn/tests/` (full suite) continues to pass — including `test_chat_ux_qj5_*.py`, `test_runner_auth.py`, `test_web_admin_auth.py`, `test_usage_auth.py`, `test_server_module_auth.py`, `test_proxy_no_body_keys.py`, and once Saturn-hft lands `test_configure_page_ui.py`.
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec start` (the start-tab spec that historically exercised the legacy `Configure New Service` form) continues to pass with no new violations. If the legacy form is removed/repurposed, Bombadil's spec needs an update — flag at PR time.
5. Visual: rodney capture of the per-service editor showing list + new-service form + edit form + delete confirmation flow. Demo's existing scaffold convention applies.

## Implementer
hardener (per athena routing — qj5.13 commit-3 lands behind Saturn-hft commit-2).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/Saturn-6sb/transcript.md`
