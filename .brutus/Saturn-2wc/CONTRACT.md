# Saturn-2wc — server-side test/validate before save

## Contract

Field validation happens server-side before any persistence. The
admin-config form and the new-service form must round-trip through
their respective validate endpoints; bad input is REJECTED, not
silently saved.

Endpoints:
- `POST /api/services/test` — live `GET <base>/models` against the
  candidate upstream, optional bearer from `api_key_env`.
- `POST /api/admin/config/validate` — schema/rule check (CIDRs, UUIDs,
  enums, range bounds).

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | Bad service base_url → `/api/services/test` `ok:false`. UI Save flow does not silently persist a service. | `a_bad_service_test_fails`: ok:false, error reports connection failure; `a_ui_no_silent_save`: 6 services before (built-ins only) |
| b | Good service (Ollama at 127.0.0.1:11434) → test `ok:true` with model count; POST `/api/services` persists; GET surfaces the new entry. | `b_good_service_test_ok`: ok:true, models 1; `b_save_persists`: post_status 200, names contains `ollama-2wc` |
| c | Bad admin config → validate returns `ok:false` with errors; POST `/api/admin/config` rejects with 422. | `c_bad_admin_rejected`: 2 errors (UUID, CIDR), save_status 422 |
| d | Good admin config → validate `ok:true`; POST persists; GET reflects values. | `d_good_admin_persists`: validate ok, save 200, rate_rpm 600, trust_mode tofu |

## Verification

- Scenario: `tests/bombadil/validate_2wc.py`
- Run: `python3 tests/bombadil/validate_2wc.py`
- Result: **PASS** — 6/6 oracle predicates true.
- Artifacts: `tests/bombadil/results/validate_2wc/result.json`.
- Real backends: bad URL = unreachable port 1; good URL = local Ollama
  on port 11434 (live `GET /v1/models`).
- No mocks. Bearer auth via `SATURN_ADMIN_TOKEN`. Isolated services
  dir + admin_config.json under tmp so no leak into the dev tree.

Status: **PASS / independent verification — Saturn-2wc.**
