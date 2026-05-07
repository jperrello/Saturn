# Hermes (NousResearch)

## Status
**Considered, rejected as a Saturn backend.** Hermes does not ship an
OpenAI-compatible inference server.

## 2026-verified survey
Repo surveyed: `github.com/NousResearch/hermes-agent`, latest tag
`v2026.4.30` (2026-04-30); `pyproject.toml:4` reports `0.12.0`; HEAD on `main`
at `3cdbf33` (2026-05-06). `requires-python>=3.11`. Install:

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
# or
pip install -e .
```

Other NousResearch candidates ruled out:

- **Hermes-Function-Calling** — CLI inference scripts (`functioncall.py`,
  `jsonmode.py`); no HTTP server.
- **atropos** — RL/training infrastructure; *consumes* an external
  OpenAI-compatible inference server (vLLM, SGLang, OpenAI), does not provide
  one.
- Remaining ~78 NousResearch repos — model weights, training code, agent
  demos, terminal/CLI tooling. None expose `/v1/*` HTTP endpoints.

## Why it is not a Saturn backend
`grep -rn "/v1/chat/completions\|/v1/models\|/v1/health"` across all `*.py`
in `hermes-agent` matches only inside provider *client* code
(`plugins/model-providers/openrouter|anthropic|bedrock`,
`hermes_cli/runtime_provider.py`) that POSTs to upstream providers.

The only HTTP listener (`hermes_cli/web_server.py:67`, `hermes web`) exposes
`/api/*` routes — UI status, sessions, config, env, model, providers/oauth,
cron. There is no `/v1/chat/completions`, no `/v1/models`, no `/v1/health`.

Subcommands:

- `hermes` — interactive CLI (`cli.py`).
- `hermes gateway` — messaging gateway (`gateway/run.py`).
- `hermes mcp serve` — **stdio** MCP server (`mcp_serve.py:1`), not HTTP.
- `hermes web` — FastAPI + Vite UI backend (`hermes_cli/web_server.py:67`).

Hermes-agent is the *inverse* of what Saturn advertises: Saturn discovers
`/v1/*` backends, hermes-agent is a *client* of one.

## Path to running a Nous-trained model behind Saturn
Wrap the GGUF / HF weights with a generic OpenAI-compatible server
(vLLM, llama.cpp `server`, SGLang, Ollama) and advertise *that* under
`_saturn._tcp.local.`. NousResearch ships weights, not servers; the Saturn
provider that actually fronts a Hermes model is whichever runner you pick,
not Hermes itself.

## Test
No test file — there is no Saturn-facing surface to exercise.
