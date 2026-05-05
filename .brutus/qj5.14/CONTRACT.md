# CONTRACT: Saturn-qj5.14 — boot validators + LLM-honoured proof tests

Bead: Saturn-qj5.14 (P1, **CENTRAL** user concern per overseer tick 3)
Branch: `autonomous/promo-push`
Spec source: `PRE_SPECS_B3.md` §17.B (geoff, 38962eb).

## Spec restatement

qj5.14 has two halves:

**Security half — boot validators (§17.B.1-3).** `saturn web` boot must call `AdminConfig.validate(cfg)`, aggregate `errors[]` from eight `_check_*` helpers (one per CONFIG_FIELDS §C row C.1.1 → C.1.8), and either `sys.exit(1)` after logging all errors OR (under `SATURN_DEV_MODE=1`) log them and continue. The validator surfaces *all* errors in one pass — admins fix in one edit, not eight reboots.

**LLM-honoured half — config-honoured-end-to-end (§17.B.4).** The user's central concern: "if I set `max_tokens=50`, does the LLM stop at 50?" Saturn passes params through; the upstream's honesty is what's asserted. Read the upstream's response (`usage.completion_tokens`, `model`, generated text) — never Saturn's internal state. Six fields (`max_tokens`, `temperature=0`, `model=<X>`, `system_prompt`, `stop=["END"]`, `top_p=0.01`) × two backends (Ollama + minted-and-revoked OpenRouter sub-key) × two creation paths (existing TOML + `POST /api/services`).

Falsifier: any boot validator triple regresses to silent acceptance OR collapses the multi-error report; OR any field/backend/path combination shows the upstream did not receive the configured value.

This is **test-only** — no implementer block. Tests sit RED until upstream beads land the validators (per §17.B.5: "Boot validators land as part of brutus's auth PR since it shares `_set_auth_secrets` plumbing"). The LLM-honoured half goes green as soon as Saturn's chat path correctly forwards the params.

## Test files
- `saturn/tests/conftest_b3.py` (new) — shared `_boot()` subprocess helper, `MIN_*` env constants
- `saturn/tests/test_boot_validators.py` (new, 27 tests — eight C.1.x triples + 2 structural + 1 loopback negative)
- `saturn/tests/test_config_honoured.py` (new, 5 tests — `max_tokens`, `model_id` × {existing, new} on Ollama; `max_tokens` on OpenRouter; OpenRouter test skips without `OPENROUTER_PROVISIONING_KEY`)

## Run command
```
cd /Users/jperr/Documents/Saturn && PATH=/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH python3 -m pytest saturn/tests/test_boot_validators.py saturn/tests/test_config_honoured.py --timeout=90
```

## Captured red output (full transcript at `.brutus/qj5.14/transcript.md`)
```
collected 32 items

20 failed, 11 passed, 1 skipped in 99.82s

Boot validators (16 failed, 11 passed, 0 skipped):
  - all "missing/bad refuses" cases fail (saturn boots without validation today)
  - all "good accepts" cases pass (semi-vacuous now; load-bearing post-fix)
  - test_validator_reports_all_errors_in_one_pass FAIL — multi-error report not built
  - test_dev_mode_logs_but_does_not_exit FAIL — SATURN_DEV_MODE wiring not present

LLM-honoured (4 failed, 0 passed, 1 skipped):
  - 4× Ollama params (max_tokens, model × existing+new) FAIL with IncompleteRead
    on /api/chat — Saturn's chat path needs the test-spec'd request shape
    (service-by-name + admin token) wired through.
  - test_max_tokens_50_honoured_by_openrouter SKIPPED — no OPENROUTER_PROVISIONING_KEY in CI env
```

## Oracle definition

### Security half — per check (C.1.1-C.1.8)

For each row in §17.B.2, three subprocess-driven assertions (`_boot(env=…)` returns `(exit_code_or_0, stderr)`; alive after 2s = code 0):

1. **Missing/unset → `code == 1`** AND stderr names the env var being missing.
2. **Bad value → `code == 1`** AND stderr describes the violation (default `"saturn"`, < 12 chars, < 32 chars, bad CIDR, world-readable TLS, bare `*` in CORS, etc.).
3. **Good value → `code == 0`** (process stays up).

Plus two structural invariants:

- `test_validator_reports_all_errors_in_one_pass`: a config with three independent failures emits ≥ 3 stderr lines.
- `test_dev_mode_logs_but_does_not_exit`: `SATURN_DEV_MODE=1` short-circuits `sys.exit(1)` but the error message still reaches stderr.

### LLM-honoured half — per (field × backend × path)

Saturn web spawned with `SATURN_DATA_DIR` + `SATURN_SERVICES_DIR` isolated under `tmp_path`; admin token + runner token + admin password seeded from constants. Service installed via either:

- **(a) existing**: write the TOML directly into `SATURN_SERVICES_DIR` before any chat call.
- **(b) new**: `POST /api/services` with the admin bearer.

`POST /api/chat` with `{service, model, messages, max_tokens, …}`. Read response JSON:

- `usage.completion_tokens <= max_tokens` (max_tokens row).
- `model` field equals or contains the requested model id (model row).
- (extension) `temperature=0` ⇒ two calls produce identical text; `system_prompt` ⇒ response contains a uniqueness probe; `stop` ⇒ response does not contain the stop string; `top_p` ⇒ "requested, not verifiable" — passing assertion is "Saturn's outbound request body included `top_p`" (currently scaffolded but not yet asserted in this contract — extend per §17.B.4 table).

OpenRouter half mints a sub-key with `limit=0.10` USD via `POST https://openrouter.ai/api/v1/keys`, configures the service with `api_key_env="OPENROUTER_TEST_KEY"`, runs the same field assertions, then `DELETE /keys/<hash>` on teardown — even if the test panics. Skipped without `OPENROUTER_PROVISIONING_KEY`.

## Out of scope (do NOT touch / explicitly NOT asserted)
- The full 6-field × 2-backend × 2-path cartesian (24 combinations). This contract delivers the canonical 4 + 1 (max_tokens, model on Ollama × {existing, new}; max_tokens on OpenRouter). Extending to all 24 is mechanical — the parametrize lists in `test_config_honoured.py` are the extension point, and §17.B.4's per-field assertion table is the script. Add as backends gain reliability.
- Saturn web start-up details (uvicorn args, stdout colour, log format).
- `SATURN_DEV_MODE` semantics beyond "bypass exit, keep logs."
- Whether validators run before or after `_load_admin_config()` reads from disk — implementer's call as long as the eight `_check_*` helpers are invoked before any `uvicorn.run`.
- Beacon `max_budget_usd` enforcement at runtime (separate from boot-validator presence) — F-2 / qj5.16.4 territory.
- TLS termination behaviour at runtime — separate bead.
- All shipped 16.x / 8v5 / qj5.1 suites must continue to pass (pytest invocation includes them in CI; this contract only adds new files).

## Acceptance
1. All tests in `saturn/tests/test_boot_validators.py` go green once the validator helpers land per §17.B.1-2.
2. All Ollama tests in `saturn/tests/test_config_honoured.py` go green once `/api/chat` accepts the spec'd request shape and forwards `max_tokens` / `model` to Ollama (already implemented in part — the IncompleteRead failure suggests the request shape needs alignment).
3. `test_max_tokens_50_honoured_by_openrouter` goes green when `OPENROUTER_PROVISIONING_KEY` is wired into CI secrets; skipped otherwise.
4. `pytest saturn/tests/` (full suite) continues to pass — no regression on shipped contracts (qj5.16.1, qj5.16.2, qj5.16.10, Saturn-8v5, qj5.16.6+.7, qj5.1, plus qj5.2/qj5.3/qj5.4/qj5.6 once they ship).
5. `tests/harness/selftest.py` continues to pass.

## Implementer
**No separate implementer block** — per overseer tick 3, qj5.14 is test-only. Greens follow incrementally as upstream beads land:
- C.1.1-C.1.4 boot validators: lands with the next auth-config PR (sibling to qj5.16.1/.2/.10).
- C.1.5 beacon budgets: with qj5.16.4 (F-2).
- C.1.6 TLS: with the TLS bead (F-7).
- C.1.7 trusted_proxies: with qj5.16.3 (F-3).
- C.1.8 CORS: with the CORS bead (F-7 follow-up).
- LLM-honoured Ollama half: as soon as `/api/chat` request shape stabilises (hardener can fix during qj5.13 lift).
- LLM-honoured OpenRouter half: as soon as `OPENROUTER_PROVISIONING_KEY` is wired into the test env.

Tests are immediately landable as red; greens are tracked per upstream-bead.

## Transcript path
`/Users/jperr/Documents/Saturn/.brutus/qj5.14/transcript.md`
