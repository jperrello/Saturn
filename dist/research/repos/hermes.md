# Hermes (NousResearch) — Saturn Backend Fact-Sheet

## Repo chosen + why
**`github.com/NousResearch/hermes-agent`** — the closest candidate in the NousResearch org that ships any HTTP server. Other candidates were ruled out:

- `Hermes-Function-Calling` — CLI inference scripts only (`functioncall.py`, `jsonmode.py`); no HTTP server.
- `atropos` — RL/training infrastructure; explicitly *consumes* an external OpenAI-compatible inference server (vLLM/SGLang/OpenAI), does not provide one.
- Remaining ~78 NousResearch repos — model weights, training code, agent demos, terminal/CLI tooling. None expose `/v1/*` HTTP endpoints.

## Bottom line for Saturn
**No NousResearch repo ships an OpenAI-compatible inference server.** Hermes-agent is an *agent runtime* and CLI/web UI that calls *out* to OpenAI-compatible providers (OpenRouter, Anthropic, Bedrock, local OpenAI-compat URLs). It is the inverse of what Saturn advertises: Saturn discovers `/v1/*` backends; hermes-agent would be a *client* of one, not a backend to mDNS-advertise.

## Install
Clone path: `~/.claude/crew/geoff/hermes/hermes-agent`
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
# or: pip install -e .  (pyproject.toml line 1, name="hermes-agent", requires-python>=3.11)
```

## Run command + flags
- `hermes` — interactive CLI (`cli.py`)
- `hermes gateway` — messaging gateway (`gateway/run.py`)
- `hermes mcp serve` — stdio MCP server (`mcp_serve.py:1`) — **stdio, not HTTP**
- `hermes web` — FastAPI+Vite web UI (`hermes_cli/web_server.py:67`)

## OpenAI-compat endpoints — NONE
Verified by `grep -rn "/v1/chat/completions\|/v1/models\|/v1/health"` across all `*.py`. Matches exist only inside provider *client* code (`plugins/model-providers/openrouter|anthropic|bedrock`, `hermes_cli/runtime_provider.py`) that POSTs to upstream providers.

The only HTTP server (`hermes_cli/web_server.py`) exposes `/api/*` routes (status, sessions, config, env, model, providers/oauth, cron) — a UI backend, not an OpenAI surface. No `/v1/chat/completions`, no `/v1/models`, no `/v1/health`.

## Version
- Latest tag: `v2026.4.30` (April 30, 2026)
- pyproject version: `0.12.0` (`pyproject.toml:4`)
- HEAD on main: `3cdbf33` (2026-05-06)

## Default host:port + override
Web UI server (`hermes_cli/web_server.py`) is the only HTTP listener. Defaults are configured via CLI flags / env on `hermes web` (host/port args). It is not a model-inference endpoint, so this is moot for Saturn.

## Recommendation for Saturn
Do **not** add hermes-agent as an mDNS-advertisable Saturn backend. To run a Nous-trained Hermes *model* behind Saturn's `_saturn._tcp.local.` advertisement, wrap the GGUF/HF weights with a generic OpenAI-compat server (vLLM, llama.cpp `server`, SGLang, ollama) and advertise that — same path as any other open-weights model. Nous ships weights, not servers.
