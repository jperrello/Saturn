# Saturn-7rr — max_budget paired with USD ↔ tokens unit selector

## Contract

Per RUN_MAY05_CONTEXT.md: max_budget gets a unit toggle (USD or
tokens). Persist unit alongside value. Both fields land in the
ServiceConfig dataclass and the on-disk TOML.

### Acceptance criteria

| # | Behavior | Evidence |
|---|----------|----------|
| a | Toggle USD→tokens persists across reload (server restart). | `a_persists_across_reload`: max_budget 5.0, max_budget_unit "tokens" after `terminate` + respawn |
| b | Numeric value retained when unit flips. | `b_initial_value` (5.0/usd) → `b_value_retained_on_flip` (5.0/tokens) |
| c | Saved TOML carries both `max_budget` and `max_budget_unit`. | `c_toml_has_both`: literal `max_budget = 5.0` and `max_budget_unit = "tokens"` in `<services>/budget7rr.toml` |

## Verification

- Scenario: `tests/bombadil/budget_7rr.py`
- Run: `python3 tests/bombadil/budget_7rr.py`
- Result: **PASS** — 4/4 oracle predicates true.
- Artifacts: `tests/bombadil/results/budget_7rr/result.json`.
- Real Web-UI on a live ephemeral port. Bearer auth. Isolated
  `SATURN_SERVICES_DIR` so the TOML write/read is observable on disk.
- "Reload" exercised by `terminate` + `wait` + respawn on the same
  port and config dir, then re-issuing GET /api/services.
- No mocks. Round-trip: POST → GET → PUT → GET → file read → restart
  → GET.

Status: **PASS / independent verification — Saturn-7rr.**
