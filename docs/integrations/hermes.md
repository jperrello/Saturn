# Hermes (NousResearch hermes-agent) + Saturn

`hermes-agent` is an OpenAI-compat **client** — a chat/agent runtime that
points at any OpenAI-shaped `/v1/chat/completions` endpoint. Saturn provides
that endpoint. This integration tells Hermes to route chat traffic through a
Saturn-discovered service.

> Research: `dist/research/hermes_client.md` (geoff)

Saturn ships a helper that emits or writes the config:

```
saturn hermes-config                            # auto-discover via mDNS, print snippet
saturn hermes-config --base-url http://x:8080/v1
saturn hermes-config --write                    # merge into $HERMES_HOME/config.yaml
```

## How Hermes is configured

Hermes reads its configuration from `$HERMES_HOME/config.yaml` (default:
`~/.hermes/config.yaml`). The Saturn override lives at:

```yaml
model:
  provider: custom
  base_url: http://saturn.local:8080/v1
  api_key: no-key-required
```

`saturn hermes-config --write` merges these keys in place — your existing
`logging:`, `model.name:`, and other top-level / sibling keys are preserved.
The `HERMES_HOME` environment variable is honored, matching
`hermes_constants.py::get_hermes_home()`.

### Dummy API key

Hermes substitutes `no-key-required` (or any non-empty placeholder) when the
key is empty, then attaches it as the `Authorization: Bearer …` header to the
upstream. Saturn does not validate these keys locally, so any non-empty value
works.

## Bypass paths — what does NOT route through Saturn

These hermes-agent surfaces hardcode OpenAI / OpenRouter and will NOT redirect
to Saturn even with `model.base_url` set:

- **TTS** (text-to-speech)
- **STT** (speech-to-text / transcription)
- **RL training loops** (`atropos`, hindsight memory)
- **Realtime voice** (the WebRTC / Realtime API path)

The integration covers `/v1/chat/completions` traffic. If you need every call
to flow through Saturn (including TTS/STT/RL/Realtime), wrap upstream of
Hermes with an HTTP proxy on `localhost` instead of relying on
`model.base_url`.

## Why we do NOT recommend `OPENAI_BASE_URL`

`hermes-agent` explicitly **skips** the `OPENAI_BASE_URL` environment variable
at `hermes_cli/runtime_provider.py:580`. Setting it has no effect; the only
override path is `config.yaml` under `model.base_url`. This is a deliberate
upstream choice — the snippet emitted by `saturn hermes-config` therefore
never references `OPENAI_BASE_URL`, and you should not set it either.

## References

- Source: `saturn/clients/hermes.py`
- Research: `dist/research/hermes_client.md` (geoff)
- Discover endpoints: `saturn discover --json`, `saturn endpoint`
- Hermes upstream: NousResearch/hermes-agent
