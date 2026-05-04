# qj5.14 — Saturn refuses to start unsafe

*2026-05-04T21:40:47Z by Showboat 0.6.1*
<!-- showboat-id: 59df7bd1-c462-40f2-8001-d7e01686abad -->

**Status: scaffold prefetched, awaiting validators.** qj5.14's security half lifts eight `_check_*` helpers (one per CONFIG_FIELDS row C.1.1–C.1.8) into the boot path of `saturn web`. Each refuses to start when the live config violates an invariant, surfacing every error in one pass so admins fix in one edit, not eight reboots. `SATURN_DEV_MODE=1` short-circuits the `sys.exit(1)` but still writes the messages to stderr.

## The user-trust angle

An admin running Saturn on a multi-tenant network needs to *see* the refusal to trust the safety story. "You forgot SATURN_ADMIN_PASSWORD; Saturn will not start" is a screen they actually read. The matrix below is what they get.

## Reproducer — 12-case violation matrix

Each case spawns `saturn web` with an `env -i`-clean environment seeded only with the case's variables (plus an isolated `SATURN_DATA_DIR`), waits 2 s, and prints either `ALIVE` (no boot-time refusal) or `exit=<code>  <stderr first relevant line>`. The script writes the violation classes in one block so the matrix reads top-to-bottom.

```bash
bash demo/recordings/qj5.14_boot_violations.sh
```

```output
── C.1.1 admin_password_env ─────────────────────────────────
(a) unset                                    ALIVE  (no boot-time refusal)
(b) default 'saturn'                         ALIVE  (no boot-time refusal)
(c) under 12 chars                           ALIVE  (no boot-time refusal)

── C.1.2 admin_token_env ────────────────────────────────────
(a) unset                                    ALIVE  (no boot-time refusal)
(b) under 32 chars                           ALIVE  (no boot-time refusal)

── C.1.3 runner_token_env ───────────────────────────────────
(a) unset                                    ALIVE  (no boot-time refusal)

── C.1.4 LAN bind without auth ──────────────────────────────
(a) bind=0.0.0.0 no auth                     ALIVE  (no boot-time refusal)
(b) bind=0.0.0.0 dev=1                       ALIVE  (no boot-time refusal)

── C.1.5 beacon needs max_budget_usd ────────────────────────
(a) beacon, no budget                        ALIVE  (no boot-time refusal)

── C.1.6 TLS pair ───────────────────────────────────────────
(a) cert without key                         ALIVE  (no boot-time refusal)

── C.1.7 trusted_proxies invalid CIDR ───────────────────────
(a) bad CIDR                                 ALIVE  (no boot-time refusal)

── C.1.8 CORS wildcard outside dev mode ─────────────────────
(a) cors='*' prod                            ALIVE  (no boot-time refusal)

── GREEN PATH (all secrets set, prod-safe defaults) ─────────
(z) good config                              ALIVE  (no boot-time refusal)
```

## Reading the matrix today

Every bad case currently reads `ALIVE` — Saturn boots silently regardless of the violation. **That is the gap qj5.14 closes.** Once §17.B.1-3 lands, rerun the script: each (a)/(b)/(c) row should turn into `exit=1  <message>`, and the green-path `(z)` row stays `ALIVE`.

## What the post-fix output should look like

Per the contract (Oracle definition, §17.B.2), each violating boot must exit code 1 with stderr that names the offending env var or value class. Example expected lines (one per row):

    SATURN_ADMIN_PASSWORD unset (refusing to start; set it or pass SATURN_DEV_MODE=1)

    SATURN_ADMIN_PASSWORD must be at least 12 chars (got 5)

    SATURN_ADMIN_TOKEN must be at least 32 chars (got 16)

    bind=0.0.0.0 with auth disabled — set SATURN_DEV_MODE=1 to override

    trusted_proxies entry invalid CIDR/IP: "not-a-cidr"

    cors_origins wildcard requires SATURN_DEV_MODE=1

## When validators land — one-step refresh

    bash demo/recordings/qj5.14_boot_violations.sh    # rerun matrix

    uvx showboat verify demo/recordings/qj5.14-boot-fail.md  # diff against this snapshot

## LLM-honoured half (qj5.14's other lane)

Separate scaffold expected once `/api/chat` request shape stabilises (per contract, hardener can fix during the qj5.13 lift). The harness already has the primitives — `tests.harness.openrouter.create/revoke` mints and revokes scoped sub-keys for the OpenRouter end-to-end pass without burning the parent key.

## Implementation pointers

- Test surface: `saturn/tests/test_boot_validators.py` (27 tests, 16 currently red), `saturn/tests/conftest_b3.py` (`_boot()` subprocess helper, MIN_* fixtures).

- Implementer landing zone: `saturn/web.py` lifespan / startup, before the `uvicorn.run` call. Per §17.B.1-3 the eight `_check_*` helpers are invoked from a single `AdminConfig.validate(cfg)` aggregator that returns `list[str]`.

- Schema rows: `saturn/web.py:1331` (AdminConfig fields the validators reference).
