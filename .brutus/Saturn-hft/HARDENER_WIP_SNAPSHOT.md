# Hardener WIP Snapshot — Saturn-hft (qj5.13 commit-2)

Captured 2026-05-04 by geoff before flush. Hardener was 38m into the bead,
fighting playwright through the `Depends(require_admin)` bearer gate on
`/api/admin/config`. Brutus is replacing the contract with an HTTP+HTML
shape (CONTRACT_v2.md). This snapshot lets the post-flush hardener resume
from his own work without re-deriving.

## Working tree at capture (uncommitted)

```
Web-UI/app.js     +153
Web-UI/index.html  +92
Web-UI/styles.css +104
saturn/web.py      +95
```

Plus an unstaged `saturn/tests/test_configure_page_ui.py` (the playwright
contract — superseded by CONTRACT_v2.md).

## What the hardener already built — keep most of it

### 1. `Web-UI/index.html` — full Admin Configure section (KEEP)

Added a tab button `#admin-configure-nav-btn` ("Admin Configure",
margin-left:auto) + a `<button id="admin-configure-btn">` on the Network
Scan tab + a complete `<section id="admin-configure-page" class="hidden
admin-configure-page">` with **eight `<fieldset class="config-section
admin-section" data-admin-group="A1..A8">`** — one per CONFIG_FIELDS group:

- **A1** General: model_filter, max_budget, budget_duration
- **A2** Auth: admin_session_ttl_s, admin_token_env, runner_token_env, admin_password_env
- **A3** Network: bind_host, runner_bind_host, trusted_proxies, cors_origins
- **A4** Rate: rate_rpm, rate_tpm, rate_concurrent_per_ip, max_budget_usd, budget_period, per_ip_max_budget_usd
- **A5** Endpoint policy: public_routes, require_auth_on_v1
- **A6** Proxy hygiene: proxy_models_method, redact_proxy_keys_in_logs
- **A7** MCP: mcp_allowed_urls, mcp_auth_token_envs
- **A8** Identity: trust_mode (`<select>` with tofu/allowlist/open), trusted_node_ids

All 22 inputs use `id="ac-<field_name>"` convention. Save/Close buttons in
`.ac-actions`. **This part matches the §17.A.A1–A8 schema verbatim and should ship.**

### 2. `Web-UI/index.html` — `Location.prototype.pathname` override script (REMOVE)

Lines 1043-1062: a `<script>` block that defines a setter on
`Location.prototype.pathname` to intercept assignments to
`/admin/configure` / `/configure` and reveal the hidden section in-place
without a real navigation. **This is playwright-fight cruft.** It exists
because `page.goto('/admin/configure')` was 401'ing through the bearer
gate; hardener tried to fake the navigation client-side. With CONTRACT_v2
dropping playwright, the override should be deleted — clients reach the
section via the `#admin-configure-nav-btn` tab click handler in app.js
(or via `#admin` hash) and the auth happens on the AJAX fetch, not the
page route.

### 3. `Web-UI/app.js` — admin-configure flow (KEEP)

`+153` lines starting `// --- Saturn-hft (qj5.13 commit-2): admin Configure page ---`:

- `AC_FIELDS` array — 22 `[name, type]` pairs matching `AdminConfig.model_fields`. Types: `string | int | float | bool | list | json`.
- `loadAdminConfigure()` — fetches `/api/admin/config` and populates inputs; skips the active-element to avoid clobbering admin-typed values mid-edit.
- `saveAdminConfigure()` — coerces inputs by type, POSTs `/api/admin/config`, on 422 inlines `<span class="field-error">` next to the offending field (matching error message → field name via `lo.includes(n)` heuristic).
- Polling: 500 ms interval calling `loadAdminConfigure()` when `_acDirty` is false. Catches live-mutation from another admin tab.
- Dirty flag toggled on `input` / `change` events.

**Ships as-is.** Note: the type-coercion logic is mirrored in two other
places (see drift risk in §Drift below).

### 4. `Web-UI/styles.css` — admin-configure styles (KEEP)

`+104` lines styling `.admin-configure-page`, `.config-section.admin-section`,
`.ac-actions`, `.field-error`. Yellow legends, dark fieldsets, red error
text — consistent with the existing Saturn-yellow palette. Ships as-is.

### 5. `saturn/web.py` — standalone `/admin/configure` HTML route (DECIDE)

`+95` lines: `_ADMIN_CONFIGURE_HTML` is a **second, independent**
single-file HTML+JS+CSS implementation of the same form, served by:

```python
@app.get("/admin/configure")
@app.get("/configure")
async def admin_configure_route():
    return HTMLResponse(_ADMIN_CONFIGURE_HTML)
```

The route has **no auth dep** on the page itself (admin still authenticates
via the inline JS's `fetch('/api/admin/config')`, which is bearer-gated).

**Why it exists:** hardener was trying to make playwright happy by
serving the form at a URL with no bearer gate, since the bearer flow
through page navigation was the 38-minute blocker.

**Decision needed in CONTRACT_v2:** ship one or the other.
- Option A — KEEP only the in-Web-UI section, DROP the `/admin/configure` route. Single source of truth in `Web-UI/`, fits with the rest of the SPA. Recommended if CONTRACT_v2 expects `/` to be the admin entrypoint.
- Option B — KEEP only the standalone HTML route, DROP the in-Web-UI section. Survives independently of the SPA (useful if the admin needs to recover from a broken Web-UI). Larger surface to maintain.
- Option C (NOT recommended) — keep both. Triples drift risk (see below).

The `_ADMIN_CONFIGURE_HTML` blob is a dead-simple inline string with all
22 fields hardcoded; it's portable but does not benefit from any of the
existing styling/components.

## Drift risk — three independent definitions of the same 22 fields

After this change, the field list lives in three places:

1. `saturn/web.py:AdminConfig.model_fields` (Pydantic source-of-truth, server-side)
2. `Web-UI/app.js:AC_FIELDS` (client-side, in-Web-UI section)
3. `saturn/web.py:_ADMIN_CONFIGURE_HTML` `FIELDS` array (client-side inside the standalone route's inline JS)

Pick Option A or B above to collapse to two. The third source of truth
(2 or 3, whichever is dropped) is then deletable.

The qj5.13 commit-1 meta-test
`test_every_admin_config_field_has_roundtrip_row` enforces (1) ↔ test
table; an analogous UI-side meta-test should enforce (1) ↔ (2 or 3) so
the next field added doesn't silently miss the UI.

## Tests

- `saturn/tests/test_configure_page_ui.py` — the v1 contract; uses
  `playwright.sync_api` + `tests.harness.web.serve()`. **Failing on
  bearer-gate / navigation interception.** CONTRACT_v2 replaces this with
  HTTP+HTML assertions (no browser). Hardener was on
  `test_admin_configure_renders_eight_groups` when the swoop hit.
- `saturn/tests/test_admin_config_qj5_13.py` (from 8b1e54d) — server-side
  schema + validators. **44/44 GREEN.** This is the load-bearing
  regression bar; the UI work doesn't touch it.

## Server-side state — green, not the blocker

`8b1e54d` already shipped the AdminConfig schema lift, validators,
apply_admin_config (live rate-bucket clearing + reclassify_discovered),
and `/api/admin/known-nodes/{attest,forget}`. Reviewed in
SECURITY_AUDIT.md context; **no server changes needed for qj5.13
commit-2 UI**.

## Recommended resume sequence for post-flush hardener

1. Read `.brutus/Saturn-hft/CONTRACT_v2.md` (HTTP+HTML, no playwright).
2. Decide Option A vs B above. Spec instinct: Option A (in-Web-UI section) ships natively in the SPA; the standalone `/admin/configure` route was scaffolding for the playwright fight and is no longer load-bearing. Delete the `_ADMIN_CONFIGURE_HTML` route + blob.
3. Delete the `Location.prototype.pathname` override script (lines 1043-1062 of `index.html`). Replace with a normal click handler on `#admin-configure-nav-btn` that toggles `.hidden` on `#admin-configure-page`.
4. Wire the qj5.13 commit-1 meta-test counterpart for AC_FIELDS — a small `pytest` that imports `saturn.web.AdminConfig` and asserts every field appears in the served `app.js` (regex-grep `AC_FIELDS`).
5. Run the new HTTP+HTML contract per CONTRACT_v2.

## Last hardener log lines (for context)

```
✽ Swooping… (39m 59s · ↓ 97.1k tokens)
[last visible action: pytest test_configure_page_ui.py::test_admin_configure_renders_eight_…]
playwright failure shape: "Execution context was destroyed, most likely
because of a navigation" + "before: about:blank / after: about:blank#blocked"
```

The pane-tail-grab (`/tmp/hardener-pane.txt`, 324 lines) shows roughly the
last 40 minutes of attempts: page.goto interception, location override
attempts, route-without-auth fallback, and the standalone HTML route as
final workaround. None of that pane content is load-bearing for the
resume; CONTRACT_v2 supersedes the whole approach.

---

*Snapshot complete. Working tree intact at capture; hardener may be
flushed safely.*
