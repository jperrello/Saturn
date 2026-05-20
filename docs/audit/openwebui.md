# Open WebUI

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
Open WebUI v0.9.2 (released 2026-04-24, tag visible in `CHANGELOG.md:8`).

- pip: `pip install open-webui` then `open-webui serve`.
- Docker:

  ```
  docker run -d -p 3000:8080 \
    -e OPENAI_API_KEY=<key> \
    -e OPENAI_API_BASE_URL=<url> \
    -v open-webui:/app/backend/data \
    --name open-webui --restart always \
    ghcr.io/open-webui/open-webui:main
  ```

Source: Open WebUI README, "How to Install"; `pyproject.toml` package name `open-webui`.

## How it points at Saturn

Open WebUI reads OpenAI-compatible endpoints from environment at first boot:

- `OPENAI_API_BASE_URL` — single endpoint (default `https://api.openai.com/v1`).
- `OPENAI_API_BASE_URLS` — **semicolon-separated** list; takes precedence over the singular form.
- `OPENAI_API_KEY` / `OPENAI_API_KEYS` — paired by index with the URL list.
- `ENABLE_OPENAI_API` (default `True`) — gates the OpenAI router.

A Saturn-discovered endpoint becomes one entry in `OPENAI_API_BASE_URLS`:

```
OPENAI_API_BASE_URLS="http://<saturn-host>:<port>/v1;https://api.openai.com/v1"
OPENAI_API_KEYS="saturn;<openai-key>"
```

Per-request routing reads `request.app.state.config.OPENAI_API_BASE_URLS`; index *N* in the URL list pairs with index *N* in the key list.

Code citations:
- `backend/open_webui/config.py:1131` — initial env read for `OPENAI_API_BASE_URL`.
- `backend/open_webui/config.py:1149-1155` — `OPENAI_API_BASE_URLS` split on `;` and wrapped in `PersistentConfig('OPENAI_API_BASE_URLS', 'openai.api_base_urls', ...)`.
- `backend/open_webui/routers/openai.py:251` — live URL list consulted on each chat-completion request (also referenced at lines 267, 291, 301).

## Known issues

**Persistence trap.** Env-var values are only read on first boot. After the initial run, the URL list lives in the DB-backed `config` table (SQLite/Postgres) as JSON under key `openai.api_base_urls`, wrapped by `PersistentConfig`. Subsequent boots ignore changed env vars — the DB value wins.

Recovery paths:

1. **Disable persistence before first boot.** Set `ENABLE_PERSISTENT_CONFIG=False`; env vars then govern every boot. Suitable for ephemeral / containerised deployments where Saturn endpoints rotate.
2. **Live update on a running instance.** POST the new URL list to the admin endpoint on the OpenAI router (`backend/open_webui/routers/openai.py`, the `/openai/urls/update`-style handler) to mutate the persisted `openai.api_base_urls`. Requires admin credentials.

Trailing `/` in `OPENAI_API_BASE_URL` is stripped by Open WebUI before use; Saturn `endpoint=` TXT values should not depend on the slash being preserved.

## Test
See `tests/integrations/test_openwebui.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
