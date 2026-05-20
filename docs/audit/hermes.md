# Hermes (NousResearch)

Saturn integrates `hermes-agent` as a **client**: Saturn writes the
endpoint into `~/.hermes/config.yaml`, Hermes reads it on launch, and the
main chat path flows through Saturn. The shape is the same as
`docs/audit/cursor.md` — a config-file integration on the user side, with
a Saturn-shipped helper that materialises the file rather than mutating
the upstream tool's binary state.

The earlier "considered, rejected" framing (commit `2dd4e81`) was
premature — it caught only the absence of an OpenAI-compat *server* in
the NousResearch ecosystem. `dist/research/hermes_client.md` (geoff)
re-surveyed the repo and found a deliberate, documented path for the
client-side case.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

NousResearch/hermes-agent v0.12.0 (`pyproject.toml`,
`requires-python = ">=3.11"`).

Canonical install (`README.md:55`):

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Or from source:

```bash
pip install -e .
```

Latest tag at survey time: `v2026.4.30` (2026-04-30); HEAD on `main`
`3cdbf33` (2026-05-06).

## How it points at Saturn

Hermes resolves the inference endpoint through a layered "runtime
provider" resolver, not a single env var. **`OPENAI_BASE_URL` is
deliberately not consulted** as a URL source — the inline comment at
`hermes_cli/runtime_provider.py:580–581` reads "OPENAI_BASE_URL env var
is no longer consulted — config.yaml is the single source of truth"
(it is read only at line 975 as a boolean "has custom endpoint" signal,
to suppress the credential pool).

The supported integration is therefore a YAML file write at
`~/.hermes/config.yaml`:

```yaml
model:
  provider: custom
  base_url: http://<saturn-host>:<port>/v1
```

Resolution path:

- `~/.hermes/` is the config root. `hermes_constants.py:14–30` —
  `get_hermes_home()` returns `$HERMES_HOME` if set, else `~/.hermes`;
  profile mode is supported via `HERMES_HOME=<root>/profiles/<name>`
  (`hermes_constants.py:80–106`). No XDG support.
- `hermes_cli/config.py:246–248` — `get_config_path()` returns
  `get_hermes_home() / "config.yaml"`. Companion `.env` at line
  `:251–252`.
- `model.base_url` is read at
  `hermes_cli/runtime_provider.py:119`
  (`base_url = (cfg.get("base_url") or "").strip()`).
- `model.provider: custom` (or `auto`) is required for `model.base_url`
  to be honored on the bare-custom path; the trust-check at
  `hermes_cli/runtime_provider.py:44–59`
  (`_config_base_url_trustworthy_for_bare_custom`) gates this.
- The OpenAI SDK is then constructed with `base_url=` from the
  resolved value (`agent/auxiliary_client.py:1230, :1265, :1532, :1593`).

The CLI `hermes model` (interactive picker) writes `model.base_url` into
`config.yaml`. There is no `--base-url` flag on the main `hermes`
entry; programmatic callers can pass `explicit_base_url` to the
resolver (`hermes_cli/runtime_provider.py:892–897`).

**Auth.** Dummy bearer accepted. Hermes substitutes `"no-key-required"`
when no real credential exists (`hermes_cli/runtime_provider.py:502,
:548, :650`; "Use a placeholder key — the OpenAI SDK requires a
non-empty string but local servers ignore the Authorization header" —
`agent/auxiliary_client.py:1452–1456`). Saturn backends need not
validate the bearer.

**Streaming.** Vanilla OpenAI Chat Completions SSE. The default
transport (`agent/transports/chat_completions.py`,
`api_mode = "chat_completions"`) is auto-selected for generic hostnames;
Codex Responses API and Anthropic Messages branches are picked only
when the resolved hostname matches `api.openai.com`, `api.x.ai`, or
ends with `/anthropic` (`hermes_cli/runtime_provider.py:62–86`). A
Saturn endpoint hits the default branch.

**Saturn-side helper.** `dist/contracts/hermes.md` (planned path; brutus
revising the contract to match this pivot) pins the Saturn CLI surface
that materialises `~/.hermes/config.yaml` for the user. The exact
subcommand name will be matched here once the contract lands; the audit
will track whatever name brutus pins.

## Known issues

- **Bypass paths hard-code OpenAI / OpenRouter and will not be
  redirected to Saturn.** Out-of-scope by design for this integration;
  if any of these matter, each needs its own override or patch.
  Sourced from `dist/research/hermes_client.md`:
  - `tools/tts_tool.py:138` — TTS defaults to
    `https://api.openai.com/v1`.
  - `tools/transcription_tools.py:92` — STT defaults to
    `https://api.openai.com/v1` (overridable via
    `STT_OPENAI_BASE_URL`).
  - `tools/rl_training_tool.py:1135` — passes
    `--openai.base_url https://openrouter.ai/api/v1` to a training
    subprocess.
  - `plugins/memory/hindsight/__init__.py:741` — hindsight memory
    provider hard-codes `https://openrouter.ai/api/v1`.
  - `plugins/google_meet/realtime/openai_client.py:24` —
    `wss://api.openai.com/v1/realtime`.
  - Named-provider plugins under `plugins/model-providers/` each
    declare a fixed `base_url=`; selecting one of those instead of
    `custom` bypasses the config file.

  The main chat path — CLI, gateway, delegate subagents — *does* flow
  through `resolve_runtime_provider` and inherits `model.base_url`
  (`tools/delegate_tool.py:984, :1979`). Subagents are not the Cursor-
  style silent-fall-back-to-cloud problem.
- **No env-var path.** Saturn cannot redirect Hermes by exporting
  `OPENAI_BASE_URL`. The integration is a file write to
  `~/.hermes/config.yaml`; behaviour follows OpenCode-shape (audit
  doc) more than Aider-shape.
- **`HERMES_HOME` profile mode.** Operators who use
  `HERMES_HOME=<root>/profiles/<name>` need Saturn to write into the
  active profile root, not the bare `~/.hermes/`. The Saturn helper
  must honour `$HERMES_HOME`.

## Note on the rejected-services registry

The `saturn.providers.hermes` stub originally landed under `2dd4e81` as
a curated-refusal mechanism (raised an explicit error rather than a
generic `ImportError`). That mechanism is still useful and is **kept**
as a generic "rejected-services" registry for any future negative-
result integration; it is no longer the Hermes integration itself.
Hermes now flows through the config-writer helper described above.

## Test
See `tests/integrations/test_hermes.py` (Saturn-f1h, contract pivot
in flight).

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | Pending revised contract + bombadil run. |
