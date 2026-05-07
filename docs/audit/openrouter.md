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
- **`requests.delete` has no timeout** (`saturn/providers/openrouter.py:28`).
  A hung TCP connection to OpenRouter can stall the rotation loop.
  [needs-research] whether the rotation loop wraps this call in its own
  timeout.

## Test
See `tests/integrations/test_openrouter.py`. In-tree coverage that exercises
the provider plumbing: `saturn/tests/test_providers.py`,
`saturn/tests/test_beacon_sleep.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
