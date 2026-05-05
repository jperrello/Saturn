# qj5.16.4 — beacon ephemeral_key budget invariants (F-2)

*2026-05-05T03:45:57Z by Showboat 0.6.1*
<!-- showboat-id: 54eedcc7-6272-47a9-82ea-6fc4536fd097 -->

**Status: shipped (commit 50750fe, qj5.16.14 co-land includes §7.5 budget plumbing).** SECURITY_AUDIT.md §7 / F-2 closed: `provider.payload()` now accepts a `max_budget_usd` kwarg that emits `limit` (OpenRouter) / `max_budget_usd` (DeepInfra) on the upstream mint; DeepInfra `revoke()` does a real DELETE; defaults adjusted so `expiration_interval ≤ rotation_interval × 1.5` (400 / 600 = 1.50, ratio at the ceiling); `AdminConfig.beacon_max_budget_usd` lands and is threaded through `CredentialManager` into the upstream payload.

## The user-trust angle

"Bonjour for AI" is only safe if the credential the LAN reads is bounded — by USD, by model, by time. Pre-fix the credential was bounded only by time, and even that horizon was wider than the rotation cadence. Post-fix the upstream mint carries the configured budget cap, the rotation/expiration ratio is at the audit's ceiling, and a leaked TXT is bounded by the smaller of the two horizons.

## Reproducer — five-step inspection (no mocks)

(1) reads the live `provider.payload()` for both providers, calls it twice — once default, once with `max_budget_usd=0.10` — and reports which cap field each provider emits. (2) shows each provider's `revoke()` body so the deepinfra real-DELETE is visible. (3) computes the rotation/expiration ratio against the freshness invariant. (4) reports whether `AdminConfig` exposes `beacon_max_budget_usd` AND whether `CredentialManager` threads it through. (5) — opt-in via `OPENROUTER_PROVISIONING_KEY` — actually mints a sub-key with `max_budget_usd=0.05`, GETs it back to inspect `limit` / `limit_remaining`, then revokes.

```bash
bash demo/recordings/qj5.16.4_beacon_probe.sh
```

```output
── (1) Provider .payload() shape — default vs plumbed budget ──
  openrouter   default-call:  {"name": "saturn-beacon-1777952759", "expires_at": "2026-05-05T03:55:59Z"}
               budget-call:   {"name": "saturn-beacon-1777952759", "expires_at": "2026-05-05T03:55:59Z", "limit": 0.1}
               accepts max_budget_usd kwarg: True    cap fields: ['limit']
  deepinfra    default-call:  {"api_key_name": "auto", "expires_delta": 600}
               budget-call:   {"api_key_name": "auto", "expires_delta": 600, "max_budget_usd": 0.1}
               accepts max_budget_usd kwarg: True    cap fields: ['max_budget_usd']

── (2) revoke() implementation surface ──
  openrouter   revoke body: 'headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}\n    try:\n        r = requests.delet' …
  deepinfra    revoke body: 'if not handle:\n        return\n    headers = {"Authorization": f"Bearer {api_key}"}\n    try:\n        r = requests.delete(' …

── (3) Freshness invariant: expiration ≤ rotation × 1.5 ──
  defaults: rotation_interval=400s  expiration_interval=600s  ratio=1.50
  PASS: expiration (600) ≤ rotation × 1.5 (600)

── (4) admin_config.beacon_max_budget_usd plumbing ──
  AdminConfig has 'beacon_max_budget_usd': True
  AdminConfig has 'max_budget_usd': True
  CredentialManager threads max_budget_usd into payload: True

── (5) Optional: real OpenRouter round-trip (uses provisioning key) ──
  POST /keys → hash=1593e719fe17…
  GET  /keys/<hash>  limit=0.05  limit_remaining=0.05  expires_at='2026-05-05T03:48:01.000Z'
  DELETE /keys/<hash>  (cleanup OK)
```

## Reading the matrix (post-fix)

- **(1) payload shape** — both providers now accept `max_budget_usd=` and emit a cap field (`limit` for OpenRouter, `max_budget_usd` for DeepInfra) when given. Default-call still omits the field for backward compat.

- **(2) revoke** — DeepInfra body flipped from `pass` to a real `requests.delete` against the scoped-jwt endpoint.

- **(3) freshness** — defaults are `rotation_interval=400`, `expiration_interval=600`. Ratio is **1.50**, exactly at the audit's ceiling. (Pre-fix was 2.00.)

- **(4) plumbing** — `AdminConfig.beacon_max_budget_usd` exists; `CredentialManager.__init__` accepts `max_budget_usd` and threads it into `provider.payload()` per source inspection.

- **(5) round-trip** — when called with `max_budget_usd=0.05` the OpenRouter upstream stores the cap; the GET reflects it. (Default-call without budget keeps `limit=None` for the existing call sites that haven't yet adopted the new kwarg — implementer's intentional default.)

## Verifying drift

    bash demo/recordings/qj5.16.4_beacon_probe.sh

    OPENROUTER_PROVISIONING_KEY=… bash demo/recordings/qj5.16.4_beacon_probe.sh   # full round-trip

    uvx showboat verify demo/recordings/qj5.16.4-beacon-budget.md

Drift gates from this snapshot: any payload regression where the budget-call no longer emits a cap field, any DeepInfra revoke flip back to a no-op body, or the freshness ratio crossing 1.5 again — all surface as a non-zero verify exit.
