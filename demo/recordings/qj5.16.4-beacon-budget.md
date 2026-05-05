# qj5.16.4 — beacon ephemeral_key budget invariants (F-2)

*2026-05-05T01:16:13Z by Showboat 0.6.1*
<!-- showboat-id: 9a55f4eb-b9b9-4ad4-bc1e-4974ce177aaa -->

**Status: scaffold prefetched, awaiting hardener.** SECURITY_AUDIT.md §7 / F-2: `BeaconAdvertiser._properties()` publishes the `ephemeral_key` directly in the mDNS TXT record so every LAN peer can read it. That's intentional — Saturn's design point is "Bonjour for AI." The risk is that the *minted* sub-key has no scoped guarantees: today's `provider.payload()` for OpenRouter and DeepInfra includes neither a USD spending cap nor a model allowlist, DeepInfra's `revoke()` is a no-op, and the default rotation×expiration ratio violates the freshness invariant `expiration ≤ rotation × 1.5`. A leaked TXT credential = leaked parent budget.

## The user-trust angle

"Bonjour for AI" is only safe if the credential the LAN reads is bounded — by USD, by model, by time. Today the credential is bounded only by time (`expires_at`), and even that horizon is wider than the rotation cadence. Admins setting `beacon_max_budget_usd` should expect Saturn to thread that cap into every minted sub-key; today it doesn't.

## Reproducer — five-step inspection (no mocks)

(1) reads the live `provider.payload()` for both providers and flags missing `limit` / model-allowlist fields. (2) shows each provider's `revoke()` body so the deepinfra no-op is visible. (3) computes the rotation/expiration ratio against the freshness invariant. (4) reports whether `AdminConfig` exposes a `beacon_max_budget_usd` field today. (5) — opt-in via `OPENROUTER_PROVISIONING_KEY` — actually mints a sub-key with the current payload, GETs it back to inspect `limit` / `limit_remaining`, then revokes.

```bash
bash demo/recordings/qj5.16.4_beacon_probe.sh
```

```output
── (1) Provider .payload() shape — what saturn asks the upstream to mint ──
  openrouter   payload={"name": "saturn-beacon-1777943775", "expires_at": "2026-05-05T01:26:15Z"}
               limit field present: False    model allowlist present: False
  deepinfra    payload={"api_key_name": "auto", "expires_delta": 600}
               limit field present: False    model allowlist present: False

── (2) revoke() implementation surface ──
  openrouter   revoke body: 'headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}\n    try:\n        r = requests.delet' …
  deepinfra    revoke body: 'pass'

── (3) Freshness invariant: expiration ≤ rotation × 1.5 ──
  defaults: rotation_interval=300s  expiration_interval=600s  ratio=2.00
  FAIL: expiration (600) > rotation × 1.5 (450)

── (4) admin_config.beacon_max_budget_usd plumbing ──
  AdminConfig has 'beacon_max_budget_usd': False
  AdminConfig has 'max_budget_usd': True
  (gate read by BeaconConfig today: NO — see saturn/runner.py:200)

── (5) Optional: real OpenRouter round-trip (uses provisioning key) ──
  POST /keys → hash=ff582c9fc642…
  GET  /keys/<hash>  limit=None  limit_remaining=None  expires_at='2026-05-05T01:18:18.000Z'
  DELETE /keys/<hash>  (cleanup OK)
```

## Reading the matrix today

- **(1) payload shape** — both providers omit `limit`. OpenRouter's `payload()` returns `{name, expires_at}` only; DeepInfra returns `{api_key_name, expires_delta}`. Neither carries a USD cap. Real round-trip (5) confirms the upstream stores `limit=None, limit_remaining=None` — the minted key has the parent's full budget.

- **(2) revoke** — OpenRouter calls `requests.delete` on `/keys/<hash>`, returns expected 200/404. DeepInfra's body is literally `pass` — leaked DeepInfra credentials live until `expires_at` regardless of what Saturn does.

- **(3) freshness** — defaults are `rotation_interval=300`, `expiration_interval=600`. Ratio is **2.00**, well above the audit's 1.5 ceiling. Saturn rotates faster than it expires; an attacker who reads a TXT credential keeps using it even after the next rotation tick.

- **(4) plumbing** — `AdminConfig` exposes `max_budget_usd` (parent budget) but not `beacon_max_budget_usd` (per-mint cap). `run_beacon` doesn't read either today.

## What the post-fix matrix should look like

    (1) openrouter   payload limit=<beacon_max_budget_usd>   model_allowlist=true

        deepinfra    payload limit=<beacon_max_budget_usd>   model_allowlist=true

    (2) deepinfra revoke body: real DELETE against the scoped-jwt endpoint

    (3) defaults adjusted: expiration_interval ≤ rotation_interval × 1.5  (e.g. 450/300 = 1.50)

    (4) AdminConfig has 'beacon_max_budget_usd': True; run_beacon plumbs it into payload

    (5) GET /keys/<hash>  limit=<value>  limit_remaining=<value>  expires_at within ratio

## Verifying drift

    bash demo/recordings/qj5.16.4_beacon_probe.sh                          # rerun

    OPENROUTER_PROVISIONING_KEY=… bash demo/recordings/qj5.16.4_beacon_probe.sh   # with real round-trip

    uvx showboat verify demo/recordings/qj5.16.4-beacon-budget.md          # diff

## Implementation pointers

- `saturn/providers/openrouter.py:12` — extend `payload(expiration)` to accept `limit` and `allowed_models`; pass through to the OpenRouter `/keys` POST body.

- `saturn/providers/deepinfra.py:9` — replace `revoke()` body with a real DELETE against `/v1/scoped-jwt/<handle>`. Confirm DeepInfra's actual revoke endpoint shape.

- `saturn/config.py:39` — adjust default `expiration_interval` so the freshness invariant holds (e.g. `int(rotation_interval * 1.5)`). Add a config validator.

- `saturn/web.py:1331` (AdminConfig) — add `beacon_max_budget_usd` field; plumb to `run_beacon` via `apply_admin_config`. Saturn-6sb's per-service `max_budget_usd` covers per-service runtime budgets; this field caps the *minted ephemeral_key budget* upstream.

- Co-landable with qj5.16.14 (sleep transition) — both touch `run_beacon`. The audit's §7.5 lists six gating fixes.
