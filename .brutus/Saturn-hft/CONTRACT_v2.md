# CONTRACT_v2: Saturn-hft — Configure page render via HTTP+HTML

Bead: Saturn-hft (P1, qj5.13 commit-2). **Supersedes CONTRACT.md** for the pytest gate; v1's playwright surface remains a useful E2E sanity but is no longer the load-bearing oracle.
Branch: `autonomous/promo-push`
Reason: v1's headless-browser navigation through the bearer-auth gate was eating hardener context (≈ 38 min, 93k tokens, "Execution context was destroyed" + about:blank#blocked). v2 drops the browser and asserts via `urllib.request` + `html.parser` only.

## Spec restatement
The admin Configure view at `GET /admin/configure` (with `Authorization: Bearer <admin_token>`) must server-render the AdminConfig schema lift across the eight CONFIG_FIELDS §A.1–A.8 groups. SPA hydration on top is fine; the underlying HTML must carry the admin-schema field markup so the test surface is independent of any JS event loop.

Five invariants — same as v1, expressed as DOM-string assertions:

- **(a)** At least one admin-schema field id/name appears in the HTML for each of CONFIG_FIELDS §A.1–A.8 (group-presence probes; rules out SPA fallback to the legacy per-service form's `cfg-*` ids).
- **(b)** Form fields render the **current** AdminConfig values inline as `value="…"` attributes — POST a known value via `/api/admin/config`, GET `/admin/configure`, parse, find an input whose `value` matches AND whose id/name/label points at the same field. Server-side pre-fill (or templated render) — not "JS fetch on mount."
- **(c)** `POST /api/admin/config {rate_rpm: 271}` returns 200; subsequent `GET /api/admin/config` returns `rate_rpm == 271`. Round-trip verifier.
- **(d)** Across all rendered form fields, every `<input>/<select>/<textarea>` whose id/name/label_text matches `/api[-_]?key/` MUST also match `/api[-_]?key[-_]?env|env[-_]?var/`. No raw API-key inputs.
- **(e)** The chat-tab HTML (served at `/`) MUST NOT carry any of the well-known admin-schema input ids (`config-rate-rpm`, `config-trusted-proxies`, etc., across the eight common variants). qj5.2 popup separation regression guard.

## Test files
- `saturn/tests/test_configure_page_http.py` (new, 5 tests — `urllib.request` + a tiny `html.parser`-based `_Probe` collector for sections + form fields. No playwright. No headless browser. ~120 lines.)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_configure_page_http.py --timeout=30
```

## Captured red output (against current HEAD, hardener's WIP)
```
collected 5 items

1 failed, 4 passed in 20.64s

PASSED test_admin_configure_renders_eight_groups
       — `ac-*` admin-schema input ids already render across all 8 groups (Bind host,
         Trusted proxies, Rate rpm, Public routes, Proxy models method, Redact proxy
         keys, MCP allowed URLs, Trust mode confirmed in Web-UI/index.html). Group-
         presence probes match.

FAILED test_section_values_populate_current_config
       — POSTs rate_rpm=137 then GETs /admin/configure; no <input> renders value="137"
         inline. Hardener's current implementation populates via JS fetch on mount,
         not server-side. v2 spec demands server-side inline.

PASSED test_post_admin_config_roundtrips
       — qj5.13 commit-1 already wired AdminConfig.rate_rpm round-trip.

PASSED test_api_key_inputs_are_env_var_names_only
       — implementer chose env-var-name labelling already; no raw key inputs.

PASSED test_chat_index_html_does_not_carry_admin_schema_ids
       — chat surface keeps qj5.2 separation; no admin ids leak.
```

The 4 already-green tests are **legitimate regression guards** under v2's HTTP+HTML semantics. The single red captures the only outstanding work: server-side value inlining.

## Oracle definition (the four green tests' shape, asserted to stay green)

### (a) `test_admin_configure_renders_eight_groups`
Module-scoped `saturn_web` fixture spins up real `python3 -m saturn web`. `GET /admin/configure` with admin bearer. Parse HTML; the joined text of every form-field id/name/label_text plus all section-heading text must contain at least one match per group's regex probe (one regex set per A.1–A.8). The probes are deliberately broad — implementer can pick their id-naming convention (e.g., `ac-*`, `config-*`, `admin-*`); any of the documented patterns satisfies. Today: matches everywhere.

### (b) `test_section_values_populate_current_config` — RED
`POST /api/admin/config {rate_rpm: 137}` (returns 200). `GET /admin/configure`. Walk `_parse(text).fields`. Find a field where `value == "137"` AND its `(id + name + label_text)` matches `/rate.?rpm|requests.*minute|\brpm\b/i`. Today: no field renders value="137" inline.

### (c) `test_post_admin_config_roundtrips`
`POST /api/admin/config {rate_rpm: 271}` returns 200; subsequent `GET /api/admin/config` returns `rate_rpm == 271`. Pure JSON-API round-trip; the UI page is irrelevant. Today: green.

### (d) `test_api_key_inputs_are_env_var_names_only`
Across all `_parse(text).fields` from `/admin/configure`, every input whose id/name/label matches `/api[-_]?key/` must ALSO match `/api[-_]?key[-_]?env|env[-_]?var/`. Today: green.

### (e) `test_chat_index_html_does_not_carry_admin_schema_ids`
`GET /` (chat surface). String-search for forbidden admin-schema ids. Today: green.

## Out of scope (do NOT touch / explicitly NOT asserted)
- Headless browser / playwright assertions. v1 keeps them as an optional E2E sanity but the contract gate is v2.
- Visual layout / styling.
- The exact id-naming convention. v2's group probes accept several common shapes.
- SPA hydration behaviour after the initial server-rendered response. v2 only asserts what the server emits.
- The chat tab's per-chat Settings popup contents (qj5.2's contract owns that).
- All shipped 16.x / 8v5 / qj5.1-6 / §17 trio test files — must continue to pass.

## Acceptance
1. All 5 tests in `saturn/tests/test_configure_page_http.py` go green. The 4 already-green tests must remain green; the 1 red (`test_section_values_populate_current_config`) closes when `/admin/configure` server-renders current AdminConfig values into `value="…"` attributes.
2. `pytest saturn/tests/` (full suite) continues to pass.
3. `tests/harness/selftest.py` continues to pass.

## Implementer
hardener — context-friendly path: ignore v1's playwright entirely; run only `test_configure_page_http.py`. The remaining work is server-side value-inlining at the `/admin/configure` template render seam.

## Transcript
A red capture against HEAD lives under `.brutus/Saturn-hft/` (v1's `transcript.md`); v2's red is reproducible via the run command above and need not be re-captured.

## Note re v1
`CONTRACT.md` (v1) and its 5-test playwright file (`saturn/tests/test_configure_page_ui.py`) remain in-tree as a manual E2E sanity surface. They are NOT the gate. If hardener wants to delete the playwright file to reduce CI time, that is acceptable — the v2 HTTP+HTML tests are the load-bearing oracle.
