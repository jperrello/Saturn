# open-webui fact-sheet

Source: https://github.com/open-webui/open-webui

## Install

- pip: `pip install open-webui` then `open-webui serve`
- Docker (OpenAI mode): `docker run -d -p 3000:8080 -e OPENAI_API_KEY=<key> -e OPENAI_API_BASE_URL=<url> -v open-webui:/app/backend/data --name open-webui --restart always ghcr.io/open-webui/open-webui:main`

(README.md, "How to Install")

## Config (env var + persistent config key)

OpenAI-compatible endpoint(s) are configured via env vars at first boot, then persisted in the DB-backed config (`PersistentConfig`):

- `OPENAI_API_BASE_URL` — single endpoint (default `https://api.openai.com/v1`).
- `OPENAI_API_BASE_URLS` — semicolon-separated list of endpoints; takes precedence over the singular form. Persisted under config key `openai.api_base_urls`.
- `OPENAI_API_KEY` / `OPENAI_API_KEYS` — paired by index with the URLs. Persisted under `openai.api_keys`.
- `ENABLE_OPENAI_API` (default `True`) — must be true for the OpenAI router to be active. Persisted under `openai.enable`.

After first run, runtime values live in the SQLite/Postgres `config` table (JSON blob) — env vars only seed initial values unless `ENABLE_PERSISTENT_CONFIG=False`. A trailing `/` in `OPENAI_API_BASE_URL` is stripped.

Refs: `backend/open_webui/config.py:1131-1155` (env load + PersistentConfig wiring).

## Version

- Latest tag: **v0.9.2** — released 2026-04-24 (CHANGELOG.md:8; `git describe` on shallow clone HEAD `8dae237`).
- pyproject name: `open-webui` (pyproject.toml).

## Startup base-URL selection

- `backend/open_webui/config.py:1131` — `OPENAI_API_BASE_URL = os.environ.get('OPENAI_API_BASE_URL', '')` (initial env read).
- `backend/open_webui/config.py:1149-1155` — splits `OPENAI_API_BASE_URLS` on `;` into a list and wraps it in `PersistentConfig('OPENAI_API_BASE_URLS', 'openai.api_base_urls', ...)` so DB values override env on later boots.
- `backend/open_webui/routers/openai.py:251,267,291,301` — request handlers read/write `request.app.state.config.OPENAI_API_BASE_URLS` to route chat-completion calls; index N in URLs is paired with index N in keys. This is the live selection used per request.

To point Open WebUI at a Saturn-discovered endpoint: either (a) set `OPENAI_API_BASE_URL=http://<saturn-host>:<port>/v1` and `OPENAI_API_KEY=<any>` before first boot, or (b) POST the URL list to the `/openai/urls/update` admin endpoint (router above) to mutate the persisted `openai.api_base_urls`.
