# Jan (menloresearch/jan) — Fact Sheet

Local-first desktop chat app (Tauri + React web-app) that talks to local llama.cpp and any OpenAI-compatible remote engine.

## Version

- Latest release: **v0.7.9**, published **2026-03-23** (commit `144b88f`).
- Source: GitHub Releases API (`/repos/menloresearch/jan/releases/latest`).

## Install

Prebuilt binaries from https://jan.ai (macOS/Windows/Linux). Build from source per `README.md`:

```
make            # installs deps, builds core, launches app (dev)
make build      # production build
# or, manually:
yarn install && yarn build && yarn dev
```

Tauri toolchain (Rust + Node/Yarn) required; Apple Silicon also needs `xcodebuild -downloadComponent MetalToolchain`.

## Config (remote engine schema + storage)

Jan does **not** store remote engines as standalone JSON files in the app-data dir. Persistence lives in **browser `localStorage`** under key **`model-provider`** (zustand `persist` middleware).

- Storage key: `web-app/src/constants/localStorage.ts:6` -> `modelProvider: 'model-provider'`
- Store: `web-app/src/hooks/useModelProvider.ts:241` (`name: localStorageKey.modelProvider`, `createJSONStorage(() => localStorage)`)

Schema for one provider entry (see `web-app/src/constants/providers.ts:27-60` and `web-app/src/types/modelProviders.d.ts:54`):

```json
{
  "active": true,
  "api_key": "",
  "base_url": "https://api.openai.com/v1",
  "provider": "openai",
  "explore_models_url": "https://platform.openai.com/docs/models",
  "settings": [
    { "key": "api-key",  "title": "API Key",  "controller_type": "input", "controller_props": {"value": "", "type": "password"} },
    { "key": "base-url", "title": "Base URL", "controller_type": "input", "controller_props": {"value": "https://api.openai.com/v1"} }
  ],
  "models": []
}
```

A Saturn-targeted entry would set `provider` to a unique name (e.g. `"saturn"`), `base_url` to the discovered `http://<host>:<port>/v1`, and any `api_key` (often empty for LAN). The `settings[].controller_props.value` for `base-url` should mirror `base_url` so the UI form stays consistent.

There is also a **Rust-side mirror** for the in-app proxy (`src-tauri/src/core/state.rs:17` `ProviderConfig { provider, api_key, api_keys, base_url, custom_headers, models }`), populated at runtime via Tauri commands `register_provider_config` / `unregister_provider_config` (`src-tauri/src/core/server/remote_provider_commands.rs:48,82`). It is **not** persisted to disk — re-registered each launch from the web-app store.

## Startup base-URL selection

At chat-time, the web-app reads the active provider from the zustand store and constructs an OpenAI-compatible client:

- `web-app/src/lib/ai-model.ts:102-110` — `createOpenAICompatible({ name: provider.provider, apiKey: provider.api_key, baseURL: provider.base_url ?? 'http://localhost:1337/v1', headers: {...} })`. Localhost/127.0.0.1 base URLs additionally get an `Origin: tauri://localhost` header.
- `web-app/src/lib/model-factory.ts:490,528,566,604,646` — same pattern in per-capability factories (chat / tools / vision / embedding / fallback default `https://api.openai.com/v1`).
- Model listing/refresh: `web-app/src/services/providers/tauri.ts:137,173` — `fetchTauri(\`${provider.base_url}/models\`, ...)` after a `base_url` required-check.

Selection order: `useModelProvider` store -> `provider.base_url` (string) -> passed straight into the AI SDK client per request. No env-var or settings.json override path.
