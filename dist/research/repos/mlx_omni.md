# mlx-omni-server — Fact Sheet

Repo: https://github.com/madroidmaq/mlx-omni-server
Local-AI inference server for Apple Silicon (MLX framework). Exposes OpenAI-compatible **and** Anthropic-compatible APIs.

## Install

```bash
pip install mlx-omni-server
```

PyPI package: `mlx-omni-server` (source: `pyproject.toml:2`). README also documents `pip install` as the canonical path; no `uvx` recipe in README.

## Run command + flags

After install, a console script is exposed (`pyproject.toml:52-53` — `mlx-omni-server = "mlx_omni_server.main:start"`):

```bash
mlx-omni-server [--host 0.0.0.0] [--port 10240] [--workers 1] \
                [--log-level info] [--cors-allow-origins "*"]
```

All flags defined in `src/mlx_omni_server/main.py:24-59`. The `start()` function calls `uvicorn.run("mlx_omni_server.main:app", host=..., port=..., workers=...)` at `main.py:90-112`.

Environment overrides:
- `MLX_OMNI_LOG_LEVEL` — log level
- `MLX_OMNI_CORS` — CORS allow-origins (read at import time, `main.py:87`)

## Endpoints exposed

FastAPI app assembled in `src/mlx_omni_server/routers.py:1-18`. Mounted routers:

| Path | Router | Source |
|---|---|---|
| `/v1/chat/completions` | OpenAI chat | `chat/openai/` |
| `/v1/models` | model list | `chat/openai/models.py` |
| `/v1/embeddings` | embeddings | `embeddings/` |
| `/v1/audio/speech` | TTS | `tts/` |
| `/v1/audio/transcriptions` | STT | `stt/` |
| `/v1/images/generations` | image gen | `images/` |
| `/anthropic/v1/*` | Anthropic-compat (messages) | `chat/anthropic/` (prefix added in `routers.py:18`) |

**No `/v1/health` endpoint.** Grep across `src/` finds zero health route — only a commented-out `exclude_paths=["/health"]` in `main.py:16`. Saturn will need to either probe `/v1/models` for liveness or patch in a health route before advertising via mDNS.

## Version

- pyproject `version = "0.5.2"` (`pyproject.toml:3`)
- No git tags in shallow clone; latest commit on default branch: `0d3814d` dated 2026-03-10.

## Default host:port + how to override

- Default bind: **`0.0.0.0:10240`** (`main.py:30,36`).
- Override via CLI: `mlx-omni-server --host 127.0.0.1 --port 8080`.
- README examples consistently use `http://localhost:10240/v1` as the OpenAI base URL and `http://localhost:10240/anthropic` as the Anthropic base URL.

## Saturn integration notes

- OpenAI-compat endpoint set is a near-superset of what Saturn currently advertises (`/v1/chat/completions`, `/v1/models`).
- Missing `/v1/health` — recommend a thin Saturn-side wrapper or upstream PR adding `@app.get("/v1/health")` returning `{"status":"ok"}` so the existing 20-second health poller works unmodified.
- Custom port for mDNS: launch with `--port <N>`; FastAPI/uvicorn binds cleanly on any free port.
- Bonus: same process can be advertised twice (e.g. `_saturn._tcp` for OpenAI on `/v1`, optional second TXT record for Anthropic on `/anthropic/v1`).
