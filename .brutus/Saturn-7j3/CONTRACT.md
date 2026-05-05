# CONTRACT: Saturn-7j3 — qj5.16.13 commit-3: known-nodes Configure-page UI

Bead: Saturn-7j3 (P2, qj5.16.13 commit-3)
Branch: `autonomous/promo-push`
Spec source: `bd show Saturn-7j3` + `SECURITY_AUDIT.md` §15.6.

## Spec restatement
Server-side known-nodes admin endpoints (`GET /api/admin/known-nodes`, `POST .../attest`, `POST .../forget`) shipped at `8b1e54d` and are 401-gated by qj5.16.13.1+.2 (44/44 verified). This contract pins the **UI surface** on the admin Configure view per §15.6 deferred commit-3:

- A `trust_mode` dropdown exposing the three modes: `tofu` (default), `allowlist`, `open` (gated by `SATURN_DEV_MODE` server-side; UI just exposes the option).
- An allowlist editor with a **pick-from-known-nodes** affordance that fetches `GET /api/admin/known-nodes` and lets the admin select from already-pinned nodes when populating `trusted_node_ids`.
- A **pending-rejections table** showing each `rejected[]` row with `expected_prefix` (first 8 of `expected_node_id`), `seen_prefix` (first 8 of `node_id`), the host that advertised the rebind, and two row-level actions:
  - **Attest** — calls `POST /api/admin/known-nodes/attest` with the seen `node_id` (admin-trusted re-pin) and clears the rejection.
  - **Forget** — calls `POST /api/admin/known-nodes/forget` for the service (drops the pin entirely; next observation re-TOFUs).
- All admin endpoints respond 401 without auth — already guaranteed server-side; the test directly exercises the three endpoints and asserts.

Falsifier: any of the three UI surfaces missing OR any of the three admin endpoints returning anything other than 401 without an `Authorization: Bearer …` header.

## Test files
- `saturn/tests/test_known_nodes_ui.py` (new, 6 tests — real Saturn web via `tests.harness.web.serve()` + headless Chromium 1400×900; 3 UI-surface assertions + 3 parametrized 401 regression guards)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_known_nodes_ui.py --timeout=90
```

## Captured red output (full transcript at `.brutus/Saturn-7j3/transcript.md`)
```
collected 6 items

3 failed, 3 passed in 41.30s

FAILED test_trust_mode_dropdown_has_three_options
       — no <select> on the admin Configure view labelled trust_mode.

FAILED test_allowlist_picker_lists_known_nodes
       — no visible region surfaces the seeded pinned-node prefix + service name.

FAILED test_rejections_table_renders_prefixes_and_actions
       — no Pending-rejections region; even when fetch is patched to return a canned
         rejection, no row with both prefixes + Attest + Forget buttons appears.

PASSED test_known_nodes_admin_endpoints_401_without_auth[GET-/api/admin/known-nodes-None]
PASSED test_known_nodes_admin_endpoints_401_without_auth[POST-/api/admin/known-nodes/attest-…]
PASSED test_known_nodes_admin_endpoints_401_without_auth[POST-/api/admin/known-nodes/forget-…]
       — server-side 401 already shipped (qj5.16.13.1+.2). Legitimate regression guards.
```

## Oracle definition

Module-scoped fixture: `tests.harness.web.serve()` spawns real `python3 -m saturn web` with admin auth seeded; headless Chromium 1400×900; `add_init_script` injects the admin token into `sessionStorage` AND adds `Authorization: Bearer <token>` on every `/api/*` fetch.

`_open_admin_configure(page)` tries `/admin/configure` and `/configure` paths and returns; the navigation entry point is implementer-flexible per Saturn-hft.

### (a) `test_trust_mode_dropdown_has_three_options`
Find a visible `<select>` whose enclosing label/id/name matches `/trust[-_\s]?mode/`. Its `<option>` set (lower-cased values OR text) must include all three of `tofu`, `allowlist`, `open`.

### (b) `test_allowlist_picker_lists_known_nodes`
Pre-seed via `POST /api/admin/known-nodes/attest` with a known service+node_id. Reload the Configure view. Some visible element's `innerText` must contain BOTH the pinned `node_id`'s first 8 chars AND the pinned service name. Tolerant matcher — implementer can render as a list, table, datalist, dropdown, or popover; any visible surface that lets the admin click-to-add satisfies.

### (c) `test_rejections_table_renders_prefixes_and_actions`
Two-step:
1. **Empty case** — page renders with a region whose heading text matches `/pending\s+rejections|rebind\s+rejected|rejections/` even when the rejected list is empty. The container must exist; its row body may be empty.
2. **Populated case** — patch `window.fetch` so the next `GET /api/admin/known-nodes` returns a canned response with one rejection: `service_name="rebind-target"`, `node_id="33…"`, `expected_node_id="22…"`, `host_seen="192.168.1.42"`. Trigger refresh (Refresh button if present, else navigation reload). Find a visible region whose `innerText` contains `rebind-target` AND the prefix `22222222` AND the prefix `33333333`. Inside that region, two visible `<button>` elements: one labelled `Attest`/`Trust`/`Accept` and one labelled `Forget`/`Reject`/`Delete`/`Remove`.

### (d) `test_known_nodes_admin_endpoints_401_without_auth` (parametrized × 3)
Direct `urllib.request` to `GET /api/admin/known-nodes`, `POST .../attest`, `POST .../forget` with no `Authorization` header. Each must respond 401. (Already-shipped behaviour from qj5.16.13.1+.2; legitimate regression guard.)

## Out of scope (do NOT touch / explicitly NOT asserted)
- Visual layout (table vs. list vs. cards) — any visible region with the required text + actions satisfies.
- Confirmation UX on Attest / Forget — implementer can use native `confirm()`, an inline button, or skip confirmation; the test only verifies the buttons EXIST. Forget is destructive but reversible (next observation re-TOFUs); Attest is admin-intentional. Both can be one-click.
- Whether the `trust_mode` dropdown ships under the same group as the allowlist editor or separately — both work as long as both surfaces exist on the admin Configure view.
- Refresh / live-update mechanics — fixture triggers reload-on-fetch-patch; production polling/SSE behaviour is out of scope.
- The exact label "Pending rejections" — heading text matching `/pending\s+rejections|rebind\s+rejected|rejections/` satisfies.
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 6 tests in `saturn/tests/test_known_nodes_ui.py` go green.
2. `pytest saturn/tests/` (full suite) continues to pass.
3. `tests/harness/selftest.py` continues to pass.
4. `tests/bombadil/run.sh --spec start` continues to pass with no new violations on the configure surface.

## Implementer
hardener (per athena routing — qj5.16.13 commit-3 lands behind Saturn-hft / Saturn-6sb on the admin Configure view).

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/Saturn-7j3/transcript.md`
