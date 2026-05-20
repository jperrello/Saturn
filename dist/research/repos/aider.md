# Aider — Fact Sheet

Repo: https://github.com/Aider-AI/aider
Clone: `~/.claude/crew/geoff/aider` (depth 1, HEAD `3ec8ec5`, 2026-04-25)

## Version

- `__version__` in `aider/__init__.py:3` = `0.86.3.dev` (current main).
- Latest GitHub Release (API): **v0.86.0**, published **2025-08-09**.
- Latest tag (incl. dev): `v0.86.3.dev`. Last stable patch tag: `v0.86.1`.
- HISTORY.md top stable entry: `### Aider v0.86.1` (HISTORY.md:21).

## Install

From README.md:105-107 the canonical install is the bootstrapper:

```bash
python -m pip install aider-install
aider-install
```

Also published as `aider-chat` on PyPI (badge link README.md:29). pipx is supported via the install docs (https://aider.chat/docs/install.html). No `pipx install aider-chat` line is in README itself.

## Config

Three layers, all read at startup in `aider/main.py:464-477`:

1. CLI flag: `--openai-api-base <URL>` (defined in `aider/args.py:76-79`).
2. Env var: `OPENAI_API_BASE` (set/read by `aider/main.py:620-621`).
3. YAML config file: `.aider.conf.yml`, search order = CWD -> git root -> `$HOME` (`aider/main.py:464-476`). Key name in YAML mirrors the flag: `openai-api-base: https://...` (sample at `aider/args_formatter.py:94`). Override path via `--config` (`aider/args.py:794`).

Precedence: CLI > env > config file (argparse + configargparse defaults).

## Startup base-URL selection

The decisive code path is in `aider/main.py:620-621`:

```python
if args.openai_api_base:
    os.environ["OPENAI_API_BASE"] = args.openai_api_base
```

Aider does not hold the base URL itself — it normalizes whatever source (flag/env/yaml) into the `OPENAI_API_BASE` environment variable, which LiteLLM (the downstream client) consumes when issuing OpenAI-compatible requests. So for Saturn's purposes:

- To redirect a running aider at an mDNS-discovered Saturn server, set `OPENAI_API_BASE=http://<host>:<port>/v1` before launch, OR pass `--openai-api-base http://<host>:<port>/v1`, OR write `openai-api-base: http://<host>:<port>/v1` into `.aider.conf.yml`.
- Companion key var: `OPENAI_API_KEY` (set via `--openai-api-key`, `aider/main.py:615-616`). Saturn deployments that don't require auth should still set a dummy key as LiteLLM expects one.
- Deprecated siblings now routed through `--set-env`: `OPENAI_API_TYPE`, `OPENAI_API_VERSION` (`aider/main.py:622-629`).

Files cited (absolute):
- `/Users/jperr/.claude/crew/geoff/aider/aider/__init__.py`
- `/Users/jperr/.claude/crew/geoff/aider/aider/args.py`
- `/Users/jperr/.claude/crew/geoff/aider/aider/main.py`
- `/Users/jperr/.claude/crew/geoff/aider/aider/args_formatter.py`
- `/Users/jperr/.claude/crew/geoff/aider/HISTORY.md`
- `/Users/jperr/.claude/crew/geoff/aider/README.md`
