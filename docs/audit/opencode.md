# OpenCode

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
OpenCode v1.14.40 (tag `277f1c7`, author date 2026-05-07). The repo publishes
no GitHub Releases — versions live as `vX.Y.Z` git tags only; older
`vscode-v0.0.x` tags are for the VS Code extension subpackage.

From `README.md:48–62`:

```bash
curl -fsSL https://opencode.ai/install | bash      # script installer
npm i -g opencode-ai@latest                        # npm/bun/pnpm/yarn
brew install anomalyco/tap/opencode                # Homebrew (recommended tap)
brew install opencode                              # Homebrew (official, lags)
```

Install-dir precedence:
`$OPENCODE_INSTALL_DIR → $XDG_BIN_DIR → $HOME/bin → $HOME/.opencode/bin`.

## How it points at Saturn

**OpenCode has no `OPENAI_BASE_URL` / `OPENAI_API_BASE` env-var override** —
`grep` over `packages/` confirms zero references. Saturn integration requires
**JSON config mutation**.

Config dir: `xdgConfig/opencode` (e.g. `~/.config/opencode/` on Linux/macOS),
overridable via `OPENCODE_CONFIG_DIR` (`packages/core/src/global.ts:12, :60`).

Files merged in this order, later wins
(`packages/opencode/src/config/config.ts:335` for candidates,
`:422–424` for the global merge):

1. `~/.config/opencode/config.json`
2. `~/.config/opencode/opencode.json`
3. `~/.config/opencode/opencode.jsonc`
4. Project-local `opencode.json` / `opencode.jsonc`, walked up from `cwd`.

The OpenAI-compatible base URL is set per-provider under
`provider.<id>.options.baseURL`. Schema:
`packages/opencode/src/config/provider.ts:79–83`
(`options.apiKey`, `options.baseURL`).

Example `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openai": {
      "options": {
        "baseURL": "http://saturn.local:8080/v1",
        "apiKey": "sk-..."
      }
    }
  }
}
```

Resolution path is `Provider.resolveSDK` at
`packages/opencode/src/provider/provider.ts:1413–1450`:

1. Shallow-clone `provider.options` (line 1419).
2. Compute `baseURL` (lines 1429–1448): if `options.baseURL` is a non-empty
   string, use it; otherwise fall back to `model.api.url` from the models.dev
   catalog. Run two substitution passes — first `s.varsLoaders[providerID]`
   (e.g. AWS-derived vars), then a generic `${ENV_VAR}` replacement against
   the process env (`envs`).
3. Assign back: `if (baseURL !== undefined) options["baseURL"] = baseURL`
   (line 1450), then merge `apiKey` and headers and instantiate the SDK.

For Bedrock specifically, `provider.ts:313–316` lets `options.endpoint` (or
`baseURL`) override the AWS endpoint. For all OpenAI-compatible providers the
override path is purely `provider.<id>.options.baseURL` in the merged config.

## Known issues

**No env-var fallback.** Saturn cannot redirect OpenCode by exporting
`OPENAI_API_BASE` — that variable is unread. Two viable patterns:

1. **Saturn writes the JSON config.** A discovery-client helper materialises
   `~/.config/opencode/opencode.json` (or a Saturn-managed dir pointed to by
   `OPENCODE_CONFIG_DIR`) with `provider.<id>.options.baseURL` set to the
   selected Saturn endpoint. Implication for `hardener`: this is config
   mutation, not pure env injection — needs file-write semantics, atomic
   replace, and a backup of any pre-existing user file.
2. **Placeholder substitution.** Because `baseURL` supports `${ENV_VAR}`
   substitution (lines 1429–1448), a user who has *already* written
   `"baseURL": "${SATURN_URL}"` into their config can be redirected with a
   plain env-var export. This requires the user to have opted in once; it is
   not a zero-config path.

Pattern (1) is the only one that works without prior user setup.

## Test
See `tests/integrations/test_opencode.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
