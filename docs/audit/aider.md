# Aider

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
Aider v0.86.0 (latest GitHub Release, published 2025-08-09); current `main` is
`v0.86.3.dev` (`aider/__init__.py:3`). Last stable patch tag: `v0.86.1`
(`HISTORY.md:21`).

Canonical install (`README.md:105–107`):

```bash
python -m pip install aider-install
aider-install
```

Also published as `aider-chat` on PyPI; `pipx install aider-chat` is documented
at `https://aider.chat/docs/install.html`.

## How it points at Saturn
Three layers, read at startup in `aider/main.py:464–477`. Precedence is
CLI > env > YAML config (argparse + configargparse defaults).

1. **CLI flag.** `--openai-api-base <URL>` (`aider/args.py:76–79`).
2. **Env var.** `OPENAI_API_BASE` (`aider/main.py:620–621`).
3. **YAML config.** `.aider.conf.yml`, search order `cwd → git root → $HOME`
   (`aider/main.py:464–476`); key name mirrors the flag,
   `openai-api-base: https://...` (sample at `aider/args_formatter.py:94`).
   Override path with `--config` (`aider/args.py:794`).

Aider does not hold the base URL itself. The decisive code path
(`aider/main.py:620–621`) normalises whichever source wins into the
`OPENAI_API_BASE` environment variable, which LiteLLM (the downstream client)
reads when issuing OpenAI-compatible requests.

To redirect a running Aider at a Saturn-discovered endpoint, any of:

```bash
aider --openai-api-base http://<saturn-host>:<port>/v1
OPENAI_API_BASE=http://<saturn-host>:<port>/v1 aider
echo 'openai-api-base: http://<saturn-host>:<port>/v1' >> ~/.aider.conf.yml
```

Companion variable: `OPENAI_API_KEY` (set via `--openai-api-key`,
`aider/main.py:615–616`). Saturn deployments without auth should still set a
dummy key — LiteLLM expects one. Deprecated siblings (`OPENAI_API_TYPE`,
`OPENAI_API_VERSION`) are now routed through `--set-env`
(`aider/main.py:622–629`).

No patch to Aider is required for Saturn integration. Env-var injection from
the discovery client is sufficient; no JSON config mutation, no admin endpoint.

## Known issues
None known beyond the LiteLLM-mandated dummy `OPENAI_API_KEY` for unauthenticated
Saturn endpoints.

## Test
See `tests/integrations/test_aider.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
