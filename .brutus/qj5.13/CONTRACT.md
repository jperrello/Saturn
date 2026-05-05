# CONTRACT: Saturn-qj5.13 — Configure page schema lift (admin_config.json + validators)

Bead: Saturn-qj5.13 (P1, broadest of the §17 trio — last per accepted order)
Branch: `autonomous/promo-push`
Spec source: `PRE_SPECS_B3.md` §17.A (geoff, 38962eb).

## Spec restatement
Today `data/admin_config.json` exposes three fields (`model_filter`, `max_budget`, `budget_duration`) and the matching `AdminConfig` Pydantic model on `saturn/web.py:1305-1308`. The lift extends this to ~22 fields covering CONFIG_FIELDS §A.2 (auth), §A.3 (network), §A.4 (rate), §A.5 (endpoint policy), §A.6 (proxy hygiene), §A.7 (MCP), §A.8 (service identity). Every new field gains:

1. A row on the `AdminConfig` BaseModel with the right type.
2. A validator entry in `AdminConfig.validate(cfg) -> list[str]` mirroring the boot rules in CONFIG_FIELDS §C.
3. A fan-out hook in `apply_admin_config(cfg)` that pushes the runtime-effective fields to their consumers (rate buckets, trust policy, public-route allowlist, etc.) without restart.
4. UI controls in `Web-UI/app.js` Configure section (out of scope for this contract — pure server-side).

The receipt: **the UI/POST changed a setting → the server is running with that setting → the next request honours it.**

Falsifier: any of the four test layers regresses — round-trip drops a field, restart loses a field, a live-applicable field needs a restart, or an invalid value sneaks past the validator and corrupts on-disk config.

## Test files
- `saturn/tests/test_admin_config_qj5_13.py` (new, 33 tests):
  - 22 round-trip parametrized rows (one per new AdminConfig field across §A.2-A.8).
  - 1 meta-test (every new AdminConfig field has a round-trip row — drift guard).
  - 1 restart-preservation test (POST → kill saturn web → respawn → GET).
  - 1 live-propagation test (`rate_rpm=2` triggers 429 without restart).
  - 8 refuse-on-invalid parametrized rows (one per CONFIG_FIELDS §C violation class).

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_admin_config_qj5_13.py --timeout=60
```

## Captured red output (full transcript at `.brutus/qj5.13/transcript.md`)
```
collected 33 items

29 failed, 4 passed in 149.98s (~2.5 min)

Round-trip failures (22): every new field POST returns 200 today (the existing
handler accepts unknown keys silently) but GET drops the field — round-trip is
lossy. Test asserts GET[field] == value; today GET[field] is None.

Meta-test failure (1): AdminConfig.model_fields == {model_filter, max_budget,
budget_duration}; the 22 new fields have not been added yet. Asserts new fields
exist; gets empty set vs. expected 22.

Restart failure (1): rate_rpm not preserved (it isn't a real field today — the
write is silently dropped on disk).

Live failure (1): rate_rpm=2 doesn't actually limit chat throughput because the
runtime rate-bucket isn't reading from admin_config.

Refuse-on-invalid failures (4): all 8 invalid values are accepted with 200
because no validator runs on POST /api/admin/config.

The 4 passes: the existing-fields path remains functional for the 3 legacy
fields, masking some refuse-on-invalid cases that don't probe new fields.
```

## Oracle definition

Module-scoped fixture: spawn `saturn web` with isolated `SATURN_DATA_DIR` + admin auth seeded. Hit `/api/admin/config` via `urllib.request` with the admin bearer.

### 17.A.4.1 round-trip (`test_field_roundtrips` parametrized)
For every (field, value) in `ROUNDTRIP_TABLE`: `POST /api/admin/config {field: value}` returns 200; subsequent `GET /api/admin/config` returns `{field: value}` (deep equality).

### Drift guard (`test_every_admin_config_field_has_roundtrip_row`)
`set(AdminConfig.model_fields) − {model_filter, max_budget, budget_duration} ⊆ {field for field, _ in ROUNDTRIP_TABLE}`. Adding a new field to `AdminConfig` without a round-trip row fails this test.

### 17.A.4.2 restart preservation (`test_config_survives_restart`)
POST `rate_rpm=99`. Terminate the saturn-web subprocess. Respawn with the same `SATURN_DATA_DIR`. GET returns `rate_rpm=99`.

### 17.A.4.3 live propagation (`test_rate_rpm_takes_effect_live`)
POST `rate_rpm=2`. Issue 4 sequential `POST /api/chat` requests. At least one returns 429 (rate-limited). No restart between the config change and the throttled request.

### 17.A.4.4 refuse-on-invalid (`test_invalid_value_refused` parametrized)
For every (field, bad_value) in `REFUSE_TABLE`: POST returns 422; subsequent GET shows the field unchanged from its pre-POST value (no partial write).

`REFUSE_TABLE` covers:
- `trusted_proxies=["not-a-cidr"]` — C.1.7 CIDR validation.
- `bind_host="999.999.999.999"` — invalid IP literal.
- `admin_session_ttl_s=30` — below 60s minimum (CONFIG_FIELDS §A.2).
- `rate_rpm=0` — below 1 (§A.4).
- `trusted_node_ids=["not-a-uuid"]` — UUID format.
- `trust_mode="open"` — requires `SATURN_DEV_MODE=1`.
- `cors_origins=["*"]` — wildcard requires `SATURN_DEV_MODE=1` (C.1.8).
- `proxy_models_method="DELETE"` — only GET/POST allowed.

## Out of scope (do NOT touch / explicitly NOT asserted)
- `Web-UI/app.js` Configure section rendering (the eight collapsible groups). Pure UI work, lands in commit 2 per §17.A.5; no pytest coverage here.
- Per-service TOML editor enhancements (CONFIG_FIELDS §B.2/B.3/B.4 fields surfaced in the existing service-row editor). Lands in commit 3 of §17.A.5.
- TLS path validation runtime semantics (cert/key file existence + mode checks). Asserted in qj5.14's boot-validator C.1.6, not here.
- Beacon `max_budget_usd` per-service enforcement at runtime. F-2 / qj5.16.4 territory.
- The shape of `apply_admin_config(cfg)`'s `dict[str, str]` "what changed live vs. what requires restart" return — not asserted; implementer's call.
- Existing 16.x / 8v5 / qj5.1 / qj5.14 / qj5.15 suites — must stay green.

## Acceptance
1. All 22 round-trip parametrized tests + the meta-test go green once `AdminConfig` is extended and `_save_admin_config` / `_load_admin_config` round-trip every field.
2. `test_config_survives_restart` goes green (already shipped behaviour for the existing 3 fields; trivially extends).
3. `test_rate_rpm_takes_effect_live` goes green once `apply_admin_config(cfg)` resizes the live `Bucket` instances per §17.A.2.
4. All 8 refuse-on-invalid tests go green once `AdminConfig.validate()` runs on every `POST /api/admin/config` and returns 422 + error list on violations.
5. `pytest saturn/tests/` (full suite) continues to pass — no regression on shipped contracts (qj5.16.x, 8v5, qj5.1, qj5.14 boot validators, qj5.15 receipt envelope).
6. `tests/harness/selftest.py` continues to pass.

## Implementer
hardener (per athena routing — same chain through qj5.2). Per §17.A.5 land in three commits:
1. Server-side: extend `AdminConfig`, write `validate()`, wire `apply_admin_config()`. Lands the 33 tests in this contract.
2. UI: render eight groups in `Web-UI/app.js`. Manual Bombadil pass.
3. Per-service editor: §B.2/B.3/B.4 fields on the existing service-row editor.

Commit 1 unblocks qj5.16.x's `admin_token_env` admin-config exposure; commit 3 can land independently once §7.5 beacon-budget plumbing is complete.

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.13/transcript.md`
