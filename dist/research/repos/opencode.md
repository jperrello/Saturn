# opencode (sst/opencode)

Open-source TUI coding agent; provider-agnostic, uses models.dev catalog with per-provider overrides.

## Install

From `README.md` (lines 48-62):

```bash
curl -fsSL https://opencode.ai/install | bash      # script installer
npm i -g opencode-ai@latest                        # npm/bun/pnpm/yarn
brew install anomalyco/tap/opencode                # Homebrew (recommended tap)
brew install opencode                              # Homebrew (official, lags)
```

Install dir precedence: `$OPENCODE_INSTALL_DIR` -> `$XDG_BIN_DIR` -> `$HOME/bin` -> `$HOME/.opencode/bin`.

## Config

Config dir: `xdgConfig/opencode` (i.e. `~/.config/opencode/` on Linux/macOS), overridable via the `OPENCODE_CONFIG_DIR` flag.
Defined at `packages/core/src/global.ts:12` and `:60`.

Files merged in this order (later wins):
1. `~/.config/opencode/config.json`
2. `~/.config/opencode/opencode.json`
3. `~/.config/opencode/opencode.jsonc`
4. Project-local `opencode.json` / `opencode.jsonc` (walked up from cwd)

See `packages/opencode/src/config/config.ts:335` (candidates) and `:422-424` (global merge).

OpenAI-compatible base URL is set per-provider under `provider.<id>.options.baseURL`. Schema:
`packages/opencode/src/config/provider.ts:79-83` (`options.apiKey`, `options.baseURL`).

Example `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openai": {
      "options": { "baseURL": "http://saturn.local:8080/v1", "apiKey": "sk-..." }
    }
  }
}
```

There is no `OPENAI_BASE_URL` / `OPENAI_API_BASE` env-var override (grep confirms no references in `packages/`). Substitution of `${ENV_VAR}` tokens inside the `baseURL` string is supported (see startup section).

## Version

Latest tag: **v1.14.40**, tagged 2026-05-07 (commit `277f1c7`, author date `2026-05-07T00:33:57Z`). The repo publishes no GitHub "releases" — versions live as `vX.Y.Z` git tags only. Older `vscode-v0.0.x` tags are for the VS Code extension subpackage.

## Startup base-URL selection

Resolution happens in `Provider.resolveSDK` at `packages/opencode/src/provider/provider.ts:1413-1450`:

1. Start from a shallow clone of `provider.options` (line 1419).
2. Compute `baseURL` (lines 1429-1448):
   - If `options.baseURL` is a non-empty string, use it.
   - Otherwise fall back to `model.api.url` (the URL the models.dev catalog ships for that provider/model).
   - Run two substitution passes: first `s.varsLoaders[providerID]` (e.g. AWS-derived vars), then a generic `${ENV_VAR}` replacement against `envs` (process env passed in).
3. Assign back: `if (baseURL !== undefined) options["baseURL"] = baseURL` (line 1450), then merge `apiKey` and headers and instantiate the SDK.

For Bedrock specifically, `provider.ts:313-316` lets `options.endpoint` (or `baseURL`) override the AWS endpoint. For all OpenAI-compatible providers the override path is purely `provider.<id>.options.baseURL` in the merged config — no env-var fallback, no autodiscovery.

Implication for Saturn: clients pointing opencode at an mDNS-discovered Saturn endpoint must write/patch `~/.config/opencode/opencode.json` (or set `OPENCODE_CONFIG_DIR` to a Saturn-managed dir). Env-var injection alone will not work unless the config's `baseURL` value already contains a `${SATURN_URL}`-style placeholder.
