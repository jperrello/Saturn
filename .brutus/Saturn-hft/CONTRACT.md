# CONTRACT: Saturn-hft — qj5.13 commit-2: Configure page UI render

Bead: Saturn-hft (P1, qj5.13 commit-2)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-hft` + `PRE_SPECS_B3.md` §17.A.5 commit 2.

## Spec restatement
Server-side schema lift + validators + `apply_admin_config()` shipped in `8b1e54d` (qj5.13 commit-1) / `26d20e1` (qj5.14 boot validators). The `AdminConfig` Pydantic model exposes ~22 fields across CONFIG_FIELDS §A.1–A.8. This contract pins the **UI render** of those eight groups on an admin Configure view, with read on mount + write round-trip + inline validation surfacing.

The current `#config-page` (`Web-UI/index.html:128`) is the per-service "Configure New Service" form. The admin server-wide schema needs its own view (a new tab, a sub-route, a sibling fieldset cluster — implementer's call) discoverable via a button/link whose visible text or aria contains `admin config | configure | server settings | admin settings`.

Five falsifiable surfaces, mapped to the user's spec letters (a)–(e):

- **(a)** The view renders ≥ 8 visible group sections (`fieldset.config-section`, `.admin-section`, or `[data-admin-group]`), one per CONFIG_FIELDS §A.1–A.8 group, with headings whose lower-cased text matches at least one keyword from the table below.
- **(b)** On mount, sections fetch `/api/admin/config` and populate inputs. The test seeds `rate_rpm=137` via API, navigates, and expects an input whose value is `137` and whose label region mentions `rate_rpm` / `requests per minute` / `rpm`.
- **(c)** Edit a field, click Save/Apply: subsequent `GET /api/admin/config` reflects the new value. UI POST must hit `/api/admin/config` with the merged delta (qj5.13 commit-1's `apply_admin_config` does the rest).
- **(d)** Submit an invalid value (`bind_host=999.999.999.999` → server returns 422): an inline error element (`.error`, `.field-error`, `.invalid-feedback`, `[aria-invalid=true]`, `.config-error`, `.err`) appears inside the `bind_host` field's region. NOT a generic toast — the user must know which field failed.
- **(e)** qj5.2's per-chat Settings popup stays separate: opening it (chat-tab Settings button) MUST NOT surface any of `rate_rpm`, `rate_tpm`, `trusted_proxies`, `cors_origins`, `admin_token_env`, `public_routes`, `tls_cert_path`, `mcp_allowed_urls`. Regression guard.

| Group | Heading keywords (any match satisfies) |
|------ |-----------------------------------------|
| A.1 Existing             | `model filter` / `budget` / `general` |
| A.2 Authentication       | `auth` / `token` / `session` |
| A.3 Network posture      | `network` / `bind` / `tls` / `cors` |
| A.4 Rate limits          | `rate` / `limit` / `throughput` |
| A.5 Endpoint policy      | `endpoint` / `public` / `route` |
| A.6 Proxy hygiene        | `proxy` / `redact` |
| A.7 MCP                  | `mcp` |
| A.8 Service identity     | `identity` / `trust` / `node` |

Falsifier: any of the five tests below failing means the UI render is incomplete or the qj5.2 separation has regressed.

## Test files
- `saturn/tests/test_configure_page_ui.py` (new, 5 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium 1400×900; admin token injected into `sessionStorage` and as `Authorization: Bearer` on every `/api/*` fetch via `add_init_script`)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_configure_page_ui.py --timeout=90 -v
```

## Captured red output (full transcript at `.brutus/Saturn-hft/transcript.md`)
```
collected 5 items

4 failed, 1 passed in 59.63s

FAILED test_admin_configure_renders_eight_groups
       — _open_admin_configure() finds no /admin/configure route and no discoverable
         admin/configure/server-settings button; the 8 group sections do not exist yet.

FAILED test_section_values_populate_from_api
       — no input shows the seeded rate_rpm=137 value (mount fetch not wired).

FAILED test_edit_save_roundtrips
       — could not locate a rate_rpm input on the admin Configure view.

FAILED test_invalid_value_shows_inline_error
       — could not locate bind_host input on the admin Configure view.

PASSED test_chat_settings_popup_does_not_show_server_wide_fields
       — qj5.2's popup correctly does NOT leak server-wide fields TODAY (admin
         Configure UI doesn't exist yet, so there's nothing to leak). Load-bearing
         post-fix as a regression guard.
```

## Oracle definition

Module-scoped fixture: `tests.harness.web.serve()` spawns real `python3 -m saturn web` with admin auth seeded; headless Chromium 1400×900; `add_init_script` injects the admin token into `sessionStorage` AND patches `window.fetch` to add `Authorization: Bearer <token>` on every `/api/*` call. This mirrors the implementer's expected flow (admin password → token in sessionStorage → authed fetches) without driving the password UI.

`_open_admin_configure(page)` tries (in order): `window.location.pathname = '/admin/configure'`, `'/configure'`, `window.location.hash = 'admin'`, `'configure'`, then a button-text fallback (`/admin\s*config|configure|server\s*settings|admin\s*settings/`). Returns `True` when ≥ 4 group sections become visible (heuristic for "we landed on the admin Configure view, not somewhere else").

### (a) `test_admin_configure_renders_eight_groups`
After `_open_admin_configure`, count visible `fieldset.config-section, .admin-section, [data-admin-group]` elements. For each of the eight `GROUP_KEYWORDS` rows, at least one heading must match. Total visible sections must be ≥ 8.

### (b) `test_section_values_populate_from_api`
Seed `POST /api/admin/config {rate_rpm: 137}`. Navigate. Find an `input/select` whose `value === '137'` and whose enclosing `label/.config-field/fieldset/.admin-section` (or its `id`/`name`) mentions rate_rpm.

### (c) `test_edit_save_roundtrips`
Find a rate_rpm input. Set its value to `271`, dispatch `input` + `change`. Click a visible button matching `/save|apply/i`. Assert `GET /api/admin/config` returns `rate_rpm == 271`.

### (d) `test_invalid_value_shows_inline_error`
Find a bind_host input. Set value to `999.999.999.999`, dispatch events. Click Save. Assert an inline error element appears inside the bind_host field's region with non-empty text.

### (e) `test_chat_settings_popup_does_not_show_server_wide_fields`
Open the chat tab, dismiss gate, click qj5.2's chat Settings button (in-viewport). Find the popup container (smallest visible positioned element holding all four style options). Its `innerText` MUST NOT contain any of: `rate_rpm`, `rate_tpm`, `trusted_proxies`, `cors_origins`, `admin_token_env`, `public_routes`, `tls_cert_path`, `mcp_allowed_urls`.

## Out of scope (do NOT touch / explicitly NOT asserted)
- Per-service TOML editor enhancements (CONFIG_FIELDS §B.2/B.3/B.4 fields surfaced in the existing service-row editor) — qj5.13 commit-3.
- The exact navigation entry point (route, tab, button text, icon). Anything `_open_admin_configure` can find satisfies the test.
- The visual layout (collapsible vs. tabbed vs. flat). Eight visible sections satisfies.
- The exact Save/Apply button label or location.
- Field-level coercion on save (e.g., type-correcting `"137"` to integer `137`) — server-side already handles via `AdminConfig` Pydantic.
- The CONFIG_FIELDS §B per-service editor for new beacon/upstream/acl fields — qj5.13 commit-3 territory.
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 5 tests in `saturn/tests/test_configure_page_ui.py` go green.
2. `pytest saturn/tests/` (full suite) continues to pass — including qj5.2's chat-tab Settings popup tests (`test_chat_ux_qj5_2.py`).
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec chat` continues to pass with no new violations on the chat tab.
5. Visual: rodney capture of the admin Configure view shows the eight groups labelled clearly per Nielsen H4 / H6.

## Implementer
hardener (per athena routing — qj5.13 commit-2 lands behind commit-1 / qj5.14 which already shipped).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/Saturn-hft/transcript.md`
