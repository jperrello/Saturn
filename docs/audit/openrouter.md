# OpenRouter

OpenRouter ships in two service definitions — a static proxy
(`openrouter.toml`, beacon off) and an ephemeral-key beacon
(`orbeacon.toml`, beacon on). Both ride on the
`saturn/providers/openrouter.py` driver.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Driver: `saturn/providers/openrouter.py` (35 lines).

```python
# saturn/providers/openrouter.py
endpoint = "https://openrouter.ai/api/v1/keys"
api_base = "https://openrouter.ai/api/v1"
```

Service files:

```toml
# saturn/services/openrouter.toml — static proxy
name       = "openrouter"
deployment = "cloud"
api_type   = "openai"
priority   = 50

[upstream]
base_url    = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"

[server]
port = 0

[beacon]
enabled = false
```

```toml
# saturn/services/orbeacon.toml — ephemeral-key beacon variant
name       = "orbeacon"
deployment = "network"
api_type   = "openai"
priority   = 10

[upstream]
base_url    = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_PROVISIONING_KEY"

[server]
port = 8090

[beacon]
enabled             = true
provider            = "openrouter"
rotation_interval   = 300
expiration_interval = 600
```

## How it points at Saturn

Saturn does not point at OpenRouter — Saturn fronts OpenRouter for the LAN.

- **Static-proxy mode (`openrouter.toml`).** Saturn reads the operator's
  `OPENROUTER_API_KEY` (`saturn/config.py:32, :69`), forwards
  `/v1/chat/completions` to `https://openrouter.ai/api/v1`, and advertises
  itself under `_saturn._tcp.local.` with `priority=50`. Every LAN client
  shares the same key.
- **Beacon mode (`orbeacon.toml`).** Saturn holds an OpenRouter
  *provisioning* key (`OPENROUTER_PROVISIONING_KEY`) that has authority to
  mint child keys. Every `rotation_interval=300` seconds Saturn calls
  `POST https://openrouter.ai/api/v1/keys` with body:

  ```json
  {
    "name": "saturn-beacon-<unix-ts>",
    "expires_at": "<now + expiration_interval>"
  }
  ```

  (`saturn/providers/openrouter.py:12–20`). The minted key is broadcast in
  TXT and consumed by clients on the LAN; the provisioning key never
  leaves the operator host. Old keys are revoked via
  `DELETE https://openrouter.ai/api/v1/keys/<hash>`
  (`saturn/providers/openrouter.py:25–34`); 200 and 404 are both treated
  as success. `expires_at` is formatted with strftime
  `%Y-%m-%dT%H:%M:%SZ`.

The driver returns `(key, hash)` from `parse(data)` — the hash is the
revocation handle.

`max_budget_usd`, when set on the beacon config (`saturn/config.py:84`),
maps to the OpenRouter `limit` field on the key-creation payload
(`saturn/providers/openrouter.py:18–19`).

## Known issues

- **Provisioning-key blast radius.** A beacon-mode operator delegates
  account-level mint authority to the Saturn host. Compromise of the host
  yields the ability to create arbitrary OpenRouter keys against the
  operator's account until the provisioning key is rotated upstream.
  Defense write-up must call this out — it is the price of zero-config
  rotation.
- **Hard-coded `endpoint`/`api_base`.** No env-var override; non-default
  OpenRouter regions or staging endpoints require source edits.
- **Revocation not retried.** A failed `DELETE` (network blip, OpenRouter
  500) leaves the prior key live until its `expires_at`
  (`saturn/providers/openrouter.py:28–32`).
- **`requests.delete` has no timeout** (`saturn/providers/openrouter.py:28`)
  — confirmed. The rotation loop does **not** wrap the call in any
  bounding timeout. The same omission appears on the credential-create
  side at `saturn/runner.py:102` (`requests.post(self.endpoint, …)`,
  also no `timeout=`). The default for `requests` is `None` — block
  indefinitely until the OS or peer drops the socket.
  `CredentialManager.cleanup()` (`saturn/runner.py:134–146`) iterates
  handles serially and calls `revoke()` on each; the per-call
  `try/except` is inside `revoke()` and catches connection errors but
  not waits. Failure modes:

  - **Rotation thread stalls.** `cleanup()` blocks → next 10 s tick of
    `rotation_loop` (`saturn/runner.py:362–377`) is delayed → no
    further rotations until the hung socket resolves. The mDNS TXT
    keeps advertising the current key past its window; clients begin
    seeing 401s only after the upstream's `expires_at` lapses.
  - **Soft key leak.** Prior handles are not deleted at OpenRouter
    while `revoke()` hangs; they expire on the upstream clock at
    `expires_at` (default 600 s).
  - **Shutdown hang.** `cleanup(final=True)` at
    `saturn/runner.py:389` runs on the main thread; a single hung
    DELETE serialises Ctrl-C until it resolves.

  Test coverage for the hang path is zero
  (`saturn/tests/test_beacon_sleep.py` uses a fake provider).
  Recommended fix: `timeout=(5, 10)` (or env-tunable) on both calls;
  consider isolating revoke onto a small executor so a slow DELETE
  cannot serialise behind subsequent rotations. Source:
  `dist/research/openrouter_revoke_timeout.md` (gullivan2). Note: the
  research file also clarifies that `rotation_interval` defaults to
  **400 s** in code (`saturn/runner.py:81`); the 300 s figure in the
  service files is a per-service override.

## Test
See `tests/integrations/test_openrouter.py`. In-tree coverage that exercises
the provider plumbing: `saturn/tests/test_providers.py`,
`saturn/tests/test_beacon_sleep.py`.

Run: `python3 -m pytest tests/integrations/test_openrouter.py --cache-clear -v`
Last run: 2026-05-06, autonomous/promo-push, 8/9 PASS, 1 SKIP.

| Scenario | Result | Notes |
|---|---|---|
| `test_openrouter_static_profile_shipped` | PASS | `openrouter.toml` shape + env-var name. |
| `test_orbeacon_profile_shipped` | PASS | `orbeacon.toml` beacon-on + provisioning-key env. |
| `test_openrouter_provider_module_importable` | PASS | endpoint/api_base constants + payload/parse/revoke surface. |
| `test_openrouter_payload_shape` | PASS | `saturn-beacon-` prefix, RFC3339-Z `expires_at`, no `limit` when budget unset. |
| `test_openrouter_payload_with_budget` | PASS | `limit` set when `max_budget_usd` passed. |
| `test_openrouter_parse_extracts_key_and_hash` | PASS | `(key, handle)` tuple from documented response shape. |
| `test_openrouter_static_config_loadable` | PASS | `load_service_config('openrouter')` returns expected. |
| `test_orbeacon_config_loadable` | PASS | `load_service_config('orbeacon')` returns expected. |
| `test_openrouter_mint_and_revoke_live` | SKIP | gated on `SATURN_INTEGRATION_LIVE=1` + `OPENROUTER_PROVISIONING_KEY`. |

**Live test gating.** The mint/revoke round-trip is intentionally
skipped by default — running it costs real OpenRouter API calls
(creates and deletes a scoped key). Operators with provisioning
credentials can enable it with:

```bash
SATURN_INTEGRATION_LIVE=1 OPENROUTER_PROVISIONING_KEY=sk-or-... \
  python3 -m pytest tests/integrations/test_openrouter.py
```
