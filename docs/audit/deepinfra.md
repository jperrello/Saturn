# DeepInfra

Beacon-only provider. Saturn mints scoped JWTs against the operator's
DeepInfra account and broadcasts them on the LAN.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Driver: `saturn/providers/deepinfra.py` (34 lines).

```python
# saturn/providers/deepinfra.py
endpoint = "https://api.deepinfra.com/v1/scoped-jwt"
api_base = "https://api.deepinfra.com/v1/openai"
```

Service file:

```toml
# saturn/services/deepinfra.toml
name       = "deepinfra"
deployment = "network"
api_type   = "openai"
priority   = 10

[upstream]
base_url    = "https://api.deepinfra.com/v1/openai"
api_key_env = "DEEPINFRA_API_KEY"

[server]
port = 8090

[beacon]
enabled             = true
provider            = "deepinfra"
rotation_interval   = 300
expiration_interval = 600
```

## How it points at Saturn

Same beacon shape as OpenRouter, but the upstream issues *scoped JWTs*
rather than long-lived keys.

Every `rotation_interval=300` seconds Saturn calls
`POST https://api.deepinfra.com/v1/scoped-jwt` with body
(`saturn/providers/deepinfra.py:11–15`):

```json
{ "api_key_name": "auto", "expires_delta": <expiration_interval> }
```

`max_budget_usd`, when set on the beacon config (`saturn/config.py:84`),
adds a `max_budget_usd` field to the same payload
(`saturn/providers/deepinfra.py:13–14`). DeepInfra returns `{ "token": … }`;
`parse(data)` returns `(token, token)` — the token itself is its own
revocation handle (`saturn/providers/deepinfra.py:18–19`).

Revocation: `DELETE https://api.deepinfra.com/v1/scoped-jwt/<token>` with
`Authorization: Bearer <provisioning-key>`, 10 s timeout
(`saturn/providers/deepinfra.py:22–33`). 200, 204, and 404 are all
treated as success.

The minted token is broadcast in TXT; LAN clients reach DeepInfra through
Saturn at `https://api.deepinfra.com/v1/openai`.

## Known issues

- **Provisioning-key blast radius.** Same caveat as OpenRouter:
  beacon-mode delegates DeepInfra mint authority to the Saturn host.
- **Token == handle.** Because `parse` returns `(token, token)`, the
  rotation loop holds the live token in memory between mint and revoke.
  This is operationally identical to other beacon providers but worth
  noting for incident response.
- **Default-true `provider="deepinfra"` advertisement.** Beacon-mode
  Saturn announces the upstream identity in TXT. LAN clients can therefore
  see which commercial back-end is fronting the service. This is by design
  but should be documented for operators who treat their upstream choice
  as confidential.
- **No driver-level retry.** A failed `DELETE` leaves a token live until
  `expires_delta` elapses.
- The `[upstream].api_key_env = "DEEPINFRA_API_KEY"` setting is consumed
  by `saturn/config.py:69` (`Upstream.api_key_env`) and read into the
  rotation loop as the provisioning key.

## Test
See `tests/integrations/test_deepinfra.py`. In-tree coverage:
`saturn/tests/test_providers.py`, `saturn/tests/test_beacon_sleep.py`.

Run: `python3 -m pytest tests/integrations/test_deepinfra.py --cache-clear -v`
Last run: 2026-05-06, autonomous/promo-push, 7/8 PASS, 1 SKIP.

| Scenario | Result | Notes |
|---|---|---|
| `test_deepinfra_profile_shipped` | PASS | `deepinfra.toml` shape, beacon-on, provider="deepinfra". |
| `test_deepinfra_provider_module_importable` | PASS | endpoint/api_base constants + payload/parse/revoke surface. |
| `test_deepinfra_payload_shape` | PASS | `api_key_name=auto`, `expires_delta` seconds, no budget by default. |
| `test_deepinfra_payload_with_budget` | PASS | `max_budget_usd` round-trips when set. |
| `test_deepinfra_parse_returns_token_twice` | PASS | DeepInfra uses the JWT itself as both key and revocation handle. |
| `test_deepinfra_revoke_no_handle_is_noop` | PASS | Defensive guard against missing handle. |
| `test_deepinfra_config_loadable` | PASS | `load_service_config('deepinfra')` returns expected. |
| `test_deepinfra_mint_and_revoke_live` | SKIP | gated on `SATURN_INTEGRATION_LIVE=1` + `DEEPINFRA_API_KEY`. |

**Live test gating.** The mint/revoke round-trip is intentionally
skipped by default — running it issues a real DeepInfra scoped-JWT
provisioning call (and a corresponding revoke). Operators with
DeepInfra credentials can enable it with:

```bash
SATURN_INTEGRATION_LIVE=1 DEEPINFRA_API_KEY=... \
  python3 -m pytest tests/integrations/test_deepinfra.py
```
