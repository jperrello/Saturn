# omlx

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
TBD

## How it points at Saturn
TBD

## Known issues
TBD

## Test
See `tests/integrations/test_omlx.py` (Saturn-0m9).

Run: `python3 -m pytest tests/integrations/test_omlx.py --cache-clear -v`
Last run: 2026-05-06, autonomous/promo-push, 9/9 PASSED.

| Scenario | Result | Duration | Notes |
|---|---|---|---|
| `test_omlx_profile_shipped` | PASS | <0.01s | `saturn/services/omlx.toml` present and parseable. |
| `test_omlx_provider_module_importable` | PASS | <0.01s | `saturn.providers.omlx` imports. |
| `test_omlx_models_proxied` | PASS | 0.02s | `/v1/models` passthrough returns upstream payload. |
| `test_omlx_chat_proxied` | PASS | 0.02s | `/v1/chat/completions` passthrough. |
| `test_omlx_embeddings_proxied` | PASS | 0.02s | `/v1/embeddings` passthrough. |
| `test_omlx_messages_proxied` | PASS | 0.02s | `/v1/messages` passthrough. |
| `test_omlx_rerank_proxied` | PASS | 0.02s | `/v1/rerank` passthrough. |
| `test_omlx_advertises_openai` | PASS | 1.84s | mDNS advertisement carries `api_type=openai`. |
| `test_omlx_config_loadable` | PASS | <0.01s | Config loader accepts shipped profile. |

All tests use the in-tree omlx fixture server (no external daemon required).
