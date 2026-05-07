# Jan

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install
Jan v0.7.9, published 2026-03-23 (commit `144b88f`), per the GitHub Releases
API (`/repos/menloresearch/jan/releases/latest`).

Prebuilt binaries for macOS, Windows, and Linux at `https://jan.ai`. Build
from source per `README.md`:

```
make            # installs deps, builds core, launches app (dev)
make build      # production build
# or, manually:
yarn install && yarn build && yarn dev
```

Tauri toolchain (Rust + Node/Yarn) required; Apple Silicon also needs
`xcodebuild -downloadComponent MetalToolchain`.

## How it points at Saturn

Jan does **not** persist remote engines as standalone JSON files in the
app-data directory. Configuration lives in **browser `localStorage`** under
key **`model-provider`**, written by a zustand `persist` middleware:

- Storage key: `web-app/src/constants/localStorage.ts:6` —
  `modelProvider: 'model-provider'`.
- Store: `web-app/src/hooks/useModelProvider.ts:241` —
  `name: localStorageKey.modelProvider`,
  `createJSONStorage(() => localStorage)`.

Schema for one provider entry
(`web-app/src/constants/providers.ts:27–60`,
`web-app/src/types/modelProviders.d.ts:54`):

```json
{
  "active": true,
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "provider": "openai",
  "explore_models_url": "https://platform.openai.com/docs/models",
  "settings": [
    { "key": "api-key",  "title": "API Key",  "controller_type": "input",
      "controller_props": {"value": "", "type": "password"} },
    { "key": "base-url", "title": "Base URL", "controller_type": "input",
      "controller_props": {"value": "https://api.openai.com/v1"} }
  ],
  "models": []
}
```

A Saturn-targeted entry sets `provider` to a unique name (e.g. `"saturn"`),
`base_url` to the discovered `http://<host>:<port>/v1`, and any `api_key`
(usually empty for LAN). The `settings[].controller_props.value` for
`base-url` should mirror `base_url` so the UI form stays consistent.

A Rust-side mirror exists for the in-app proxy
(`src-tauri/src/core/state.rs:17` —
`ProviderConfig { provider, api_key, api_keys, base_url, custom_headers, models }`),
populated at runtime via the Tauri commands `register_provider_config` /
`unregister_provider_config`
(`src-tauri/src/core/server/remote_provider_commands.rs:48, :82`). It is
**not** persisted to disk — re-registered each launch from the web-app store.

At chat time the web-app reads the active provider from the zustand store
and constructs an OpenAI-compatible client at
`web-app/src/lib/ai-model.ts:102–110`:

```
createOpenAICompatible({
  name: provider.provider,
  apiKey: provider.api_key,
  baseURL: provider.base_url ?? 'http://localhost:1337/v1',
  headers: { ... }
})
```

Localhost / `127.0.0.1` base URLs additionally receive an
`Origin: tauri://localhost` header — friendly to Saturn endpoints reached on
the same host. Per-capability factories follow the same pattern at
`web-app/src/lib/model-factory.ts:490, :528, :566, :604, :646`. Model
listing/refresh: `web-app/src/services/providers/tauri.ts:137, :173`,
`fetchTauri(\`${provider.base_url}/models\`, …)` after a `base_url`
required-check.

## Known issues

**Hard integration — no file-drop config, no env-var override.** Saturn
cannot configure Jan by writing a file under `~/.config/jan/` or by exporting
an environment variable; the only persistence channel is browser
`localStorage` inside the Tauri WebView. Two viable injection paths:

1. **Write `localStorage` from inside the WebView.** A Saturn-aware
   companion script executed in the Jan WebView (e.g. via a developer-
   console paste or a bundled bookmarklet equivalent) sets the
   `model-provider` key directly. Survives restart because zustand `persist`
   re-hydrates from `localStorage` on load.
2. **Ship a Tauri extension that calls `register_provider_config`.** The
   Rust command at
   `src-tauri/src/core/server/remote_provider_commands.rs:48` accepts a
   `ProviderConfig` and registers it for the current session. Not persisted
   — must be replayed each launch — but does not require the user to touch
   the WebView.

Source: `dist/research/repos/jan.md` (geoff fact-sheet).

## Test
See `tests/integrations/test_jan.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
