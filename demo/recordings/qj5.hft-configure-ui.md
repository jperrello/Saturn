# Saturn-hft (qj5.13 commit-2) — Configure page UI render

*2026-05-05T00:43:58Z by Showboat 0.6.1*
<!-- showboat-id: ecc96813-6752-4005-a134-7888d2ef1e2e -->

**Status: shipped (commit 70f7beb, Saturn-hft v2). Open regression: qj5.13.7 P1.** Server-side AdminConfig schema lift + validators + apply hook were in place (qj5.13 commit-1 8b1e54d; qj5.14 boot validators 26d20e1). v2 lands a server-rendered `/admin/configure` (and `/configure`) route that reads `AdminConfig.model_fields` from the live config and inlines current values into the eight `fieldset.config-section` groups. **The route was supposed to require the `require_admin` bearer dependency; geoff caught at b38b4af that Saturn-6sb dropped that `Depends(require_admin)`. The route now SSR-leaks admin posture (trusted_proxies, CIDRs, cors_origins, env-var names, rate_*) to any LAN peer with no authentication.** Hardener pivoting to qj5.13.7 to restore the gate. The probe below now carries a no-bearer regression guard so the same leak never resurfaces.

## The user-trust angle

Server-wide settings (rate limits, bind host, TLS, MCP allow-list, trust mode) belong on a Configure page the admin actually navigates to and edits — not just an API the admin must POST to with curl. The five falsifiable surfaces from the contract: (a) ≥ 8 group sections render, (b) values populate from /api/admin/config on mount, (c) edit + save round-trips, (d) invalid values surface inline, (e) qj5.2's per-chat Settings popup stays separate from server-wide fields.

## Before — HEAD without Saturn-hft

Captured by reverting Web-UI/{index.html, app.js, styles.css} to commit cc92207 (parent of bb3d259). At that revision, `/admin/configure` doesn't resolve and only the legacy per-service "Configure New Service" form is visible (3 fieldsets — Service Identity / Connection / Advanced). Two of the eight group keywords match incidentally elsewhere on the page; six are absent.

```bash {image}
demo/recordings/qj5.hft-before-fullpage.png
```

![9ac81e81-2026-05-05](9ac81e81-2026-05-05.png)

Before-probe output:

    resolved url: None

    visible admin sections: 3 (legacy form only)

    A.1 General [ ]   A.2 Auth [ ]   A.3 Network [X]   A.4 Rate [ ]

    A.5 Endpoint [ ]  A.6 Proxy [ ]  A.7 MCP [ ]       A.8 Identity [X]

    GET /api/admin/config (post-seed): rate_rpm=137

## After — Saturn-hft v2 at HEAD

Probe resolves to `/admin/configure` and finds 8 visible `.config-section` groups (the dedicated server-rendered route — no legacy per-service form on this page). All eight CONFIG_FIELDS §A.1–A.8 group keywords match. The seeded `rate_rpm=137` is **inlined into the rendered HTML** before the page is served — no client-side fetch round-trip needed for first paint.

```bash {image}
demo/recordings/qj5.hft-after-fullpage.png
```

![5e436b40-2026-05-05](5e436b40-2026-05-05.png)

After-probe output (live, this commit):

```bash
bash demo/recordings/qj5.hft_probe.sh
```

```output
resolved url: http://127.0.0.1:58896/admin/configure
visible admin sections: 9
  - heading='GENERAL — MODEL FILTER & BUDGET'        text_len=74
  - heading='AUTHENTICATION — TOKENS & SESSION'      text_len=117
  - heading='NETWORK POSTURE — BIND, TLS, CORS'      text_len=136
  - heading='RATE LIMITS & THROUGHPUT'               text_len=164
  - heading='ENDPOINT POLICY — PUBLIC ROUTES'        text_len=85
  - heading='PROXY HYGIENE & REDACT'                 text_len=70
  - heading='MCP — ALLOWED URLS & AUTH ENV'          text_len=93
  - heading='SERVICE IDENTITY — TRUST MODE & NODE IDS' text_len=115
  - heading='PER-SERVICE EDITOR — SERVICES'          text_len=43
  [X] A.1 General  keywords=['model filter', 'budget', 'general']
  [X] A.2 Auth  keywords=['auth', 'token', 'session']
  [X] A.3 Network  keywords=['network', 'bind', 'tls', 'cors']
  [X] A.4 Rate  keywords=['rate', 'limit', 'throughput']
  [X] A.5 Endpoint  keywords=['endpoint', 'public', 'route']
  [X] A.6 Proxy  keywords=['proxy', 'redact']
  [X] A.7 MCP  keywords=['mcp']
  [X] A.8 Identity  keywords=['identity', 'trust', 'node']

GET /api/admin/config (post-seed): rate_rpm=137
```

## Reproducer

    bash tests/harness/run.sh                 # smoke first

    LABEL=after  PYTHONPATH=. python3 demo/recordings/_capture_qj5_hft.py

    git checkout cc92207 -- Web-UI/          # before-state

    LABEL=before PYTHONPATH=. python3 demo/recordings/_capture_qj5_hft.py

    git checkout HEAD -- Web-UI/             # restore

## Implementation pointers (post-shipped)

- Server route: `saturn/web.py:1525` — `@app.get('/admin/configure')` and `/configure`, gated by `require_admin`. Reads `AdminConfig.model_fields` from `_load_admin_config()` and inlines values into a parsed-out copy of the `#admin-configure-page` section, then wraps with a minimal HTML shell pointing at `/styles.css` + `/app.js` (module).

- Markup source of truth: `Web-UI/index.html` `<section id="admin-configure-page">` block — eight `fieldset.config-section` groups, one per CONFIG_FIELDS §A.1–A.8 row, with `#ac-<field>` inputs whose `id` matches `AdminConfig.model_fields`.

- Probe wiring: `page.context.set_extra_http_headers({Authorization: Bearer <token>})` is required for top-level navigations to /admin/configure (the route checks the bearer; no SPA fallback). `add_init_script` continues to wire window.fetch for any client-side calls. See demo/recordings/_capture_admin_lib.py.

- Test surface: `saturn/tests/test_configure_page_ui.py` (5 v2 HTTP+HTML tests, 5/5 GREEN per hardener transcript).

## Regression guard — qj5.13.7 (no-bearer SSR leak)

After geoff's review, the probe also fires three raw `urllib` requests with NO Authorization header against `/admin/configure`, `/configure`, and `/api/admin/config`. All three must return **401**. Today `/admin/configure` and `/configure` return 200 with the full admin posture inlined — that is exactly the qj5.13.7 leak.

```bash
bash demo/recordings/qj5.hft_probe.sh 2>&1 | tail -6
```

```output
GET /api/admin/config (post-seed): rate_rpm=137

no-bearer probes (must all be 401):
  /admin/configure                 200  LEAK  fields=['trusted_proxies', 'cors_origins', 'rate_rpm', 'rate_tpm', 'trusted_node_ids', 'admin_token_env', 'runner_token_env', 'admin_password_env']
  /configure                       200  LEAK  fields=['trusted_proxies', 'cors_origins', 'rate_rpm', 'rate_tpm', 'trusted_node_ids', 'admin_token_env', 'runner_token_env', 'admin_password_env']
  /api/admin/config                401  (gated)
```

## What the post-fix matrix should look like

    no-bearer probes (must all be 401):

      /admin/configure                 401  (gated)

      /configure                       401  (gated)

      /api/admin/config                401  (gated)

Once qj5.13.7 restores `Depends(require_admin)` on `admin_configure_route` (`saturn/web.py:1525`), rerun the probe — all three lines should read 401, and `uvx showboat verify` against this snapshot will surface any future drop of the gate as a non-zero verify exit.
