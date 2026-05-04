# qj5.14 — Saturn refuses to start unsafe

*2026-05-04T22:15:32Z by Showboat 0.6.1*
<!-- showboat-id: 47691bab-6e9a-4e7f-9a5a-40d021619690 -->

**Status: shipped (commit 26d20e1).** Saturn web boot calls `AdminConfig.validate(cfg)` before `uvicorn.run`; the eight `_check_*` helpers (one per CONFIG_FIELDS row C.1.1–C.1.8) refuse the boot when a security invariant is violated, surfacing every error in one pass. `SATURN_DEV_MODE=1` short-circuits the `sys.exit(1)` but still writes the messages to stderr.

## The user-trust angle

An admin running Saturn on a multi-tenant network needs to *see* the refusal to trust the safety story. "You forgot SATURN_ADMIN_PASSWORD; Saturn will not start" is a screen they actually read. The matrix below is what they get.

## Reproducer — 12-case violation matrix (post-fix)

Each case spawns `saturn web` with an `env -i`-clean environment seeded only with the case's variables (plus an isolated `SATURN_DATA_DIR` and, for C.1.5, an isolated `SATURN_SERVICES_DIR`), waits 2 s, and prints either `ALIVE` (no boot-time refusal) or `exit=<code>  <stderr first relevant line>`.

```bash
bash demo/recordings/qj5.14_boot_violations.sh
```

```output
── C.1.1 admin_password_env ─────────────────────────────────
(a) unset                                    exit=1    saturn: config error: SATURN_ADMIN_PASSWORD unset
(b) default 'saturn'                         exit=1    saturn: config error: SATURN_ADMIN_PASSWORD is the default "saturn" — change it
(c) under 12 chars                           exit=1    saturn: config error: SATURN_ADMIN_PASSWORD shorter than 12 chars (too short)

── C.1.2 admin_token_env ────────────────────────────────────
(a) unset                                    exit=1    saturn: config error: SATURN_ADMIN_TOKEN unset
(b) under 32 chars                           exit=1    saturn: config error: SATURN_ADMIN_TOKEN shorter than 32 chars (too short)

── C.1.3 runner_token_env ───────────────────────────────────
(a) unset                                    exit=1    saturn: config error: SATURN_RUNNER_TOKEN unset

── C.1.4 LAN bind without auth ──────────────────────────────
(a) bind=0.0.0.0 no auth                     exit=1    saturn: config error: SATURN_ADMIN_PASSWORD unset
(b) bind=0.0.0.0 dev=1                       ALIVE  (no boot-time refusal)

── C.1.5 beacon needs max_budget_usd ────────────────────────
(a) beacon, no budget                        exit=1    saturn: config error: beacon service probe: max_budget_usd missing

── C.1.6 TLS pair ───────────────────────────────────────────
(a) cert without key                         exit=1    saturn: config error: tls_cert_path set but tls_key_path missing

── C.1.7 trusted_proxies invalid CIDR ───────────────────────
(a) bad CIDR                                 exit=1    saturn: config error: trusted_proxies entry invalid CIDR: 'not-a-cidr'

── C.1.8 CORS wildcard outside dev mode ─────────────────────
(a) cors='*' prod                            exit=1    saturn: config error: cors_origins wildcard "*" forbidden; set SATURN_DEV_MODE=1 to allow

── GREEN PATH (all secrets set, prod-safe defaults) ─────────
(z) good config                              ALIVE  (no boot-time refusal)
```

## Reading the matrix

Every violation row reads `exit=1  saturn: config error: …`. Two rows correctly stay `ALIVE`:

- **C.1.4 (b)** `bind=0.0.0.0 dev=1` — the legitimate `SATURN_DEV_MODE=1` escape hatch documented in §17.B.3.

- **(z) good config** — the green-path baseline (all secrets ≥ length minima, prod-safe defaults).

## Verifying drift

    bash demo/recordings/qj5.14_boot_violations.sh

    uvx showboat verify demo/recordings/qj5.14-boot-fail.md  # diff against this snapshot

Any regression — a row that used to refuse now ALIVE, a stderr message that's lost its env-var anchor, a green path that started refusing — surfaces as a non-zero verify exit.

## LLM-honoured half (qj5.14's other lane)

Boot validators are one of two halves. The other proves the chat path actually forwards `max_tokens` / `model` / `temperature` / `system_prompt` / `stop` / `top_p` to the upstream — covered by `saturn/tests/test_config_honoured.py`. The harness already mints + revokes scoped OpenRouter sub-keys via `tests.harness.openrouter` so the keyed end-to-end runs without burning the parent key.

## Implementation pointers

- Validators: `saturn/web.py:1543` (`_check_admin_password_env`) → `saturn/web.py:1626` (`_check_cors_no_wildcard`); aggregator at `saturn/web.py:1635`-ish.

- Test surface: `saturn/tests/test_boot_validators.py` (27 tests, 0 red post-26d20e1) — `saturn/tests/conftest_b3.py` provides the `_boot()` subprocess helper and MIN_* constants.

- Green-path baseline mirrors `tests.harness.web.serve()` defaults (`SATURN_ADMIN_TOKEN` 32+ chars, `SATURN_ADMIN_PASSWORD` 12+ chars, `SATURN_BIND_HOST=127.0.0.1`).
