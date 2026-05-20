# Cursor

Saturn's Cursor integration is a **doc-snippet generator**, not a config
writer. Cursor's "Override OpenAI Base URL" is configured exclusively
through the IDE GUI (`Settings → Models`), with values persisted to
Cursor's encrypted Electron state. There is no public `settings.json` key
to mutate from disk. Saturn ships `saturn cursor-snippet`, a CLI that
emits the GUI instructions a user must follow by hand.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Cursor IDE, 2026 builds (forum reports cite Cursor 2.4.22 Universal on
macOS and `cursor_2.1.32_amd64.deb` on Linux).

The Cursor IDE settings file at
`~/Library/Application Support/Cursor/User/settings.json` (macOS) is the
VS Code-derived user-settings surface. Forum sources confirm the OpenAI
base-URL override is **not** stored here under any documented key.
Anything claiming a public JSON key for the override is extrapolating from
VS Code (see "Contested" in `dist/research/cursor_config.md`).

Saturn-side: `saturn cursor-snippet` CLI. Brutus contract for the snippet
shape lands as `Saturn-5pe`; cite `tests/integrations/test_cursor.py` once
the contract path is committed.

## How it points at Saturn

GUI flow (sourced verbatim from forum thread #5 in
`dist/research/cursor_config.md`):

1. `Cursor Settings → Models`.
2. Set "OpenAI API Key" to any non-empty string. Cursor attaches it as
   `Authorization: Bearer <key>` and does not validate locally; for
   unauthenticated Saturn LAN endpoints, dummy values such as `sk-no-auth`,
   `sk-dummy`, or `not-needed` are accepted. An empty string fails form
   validation.
3. Toggle "Override OpenAI Base URL".
4. Enter the Saturn-discovered prefix — the URL root onto which Cursor
   appends `/chat/completions` and `/models`, e.g.
   `http://saturn.local:8080/v1`.
5. Click "+ Add Model" and enter the model name. Cursor performs a
   server-side validation by hitting `/v1/models` (or streaming a probe);
   if the endpoint does not list/accept the model, "Add" silently fails.

`saturn cursor-snippet` emits these five steps with the Saturn endpoint
already substituted in. The user copy-pastes; the Saturn CLI never touches
the Cursor IDE state.

## Known issues

All sourced from `dist/research/cursor_config.md` (gullivan2):

- **Ask mode required.** In *Agent* mode Cursor emits a Responses-API
  payload (`input` plus flat `tools`) to `/v1/chat/completions` and
  expects Chat-Completions SSE chunks (`choices[].delta`) back. The
  endpoint must speak both, or the Saturn proxy must translate. Forum
  workaround: use **Ask mode**, which sends Chat-Completions format.
  Sources: forum #2, #3, #8.
- **HTTP/1.1 only.** HTTP/2 trips errors against custom endpoints.
  Operators must flip
  `Cursor Settings → Network → HTTP Compatibility Mode → HTTP/1.1`.
  Saturn proxies should accept both. Source: forum #4.
- **Subagents bypass the override.** Only the main agent pane uses the
  custom base URL and model registry; subagents silently fall back to
  cloud OpenAI. A Saturn-routed Cursor session is partial. Source:
  forum #6.
- **No public settings.json key for the Base URL.** Saturn cannot ship a
  config writer. Override values live in Cursor's encrypted Electron
  state (`app.getPath('userData')`); there is no documented disk key.
  Sources: forum #5, #7; absence in `docs.cursor.com` per
  `dist/research/cursor_config.md`.
- **`/v1/models` validation gate.** The Add-Model step requires the
  Saturn endpoint to list the chosen ID through `/v1/models`. A Saturn
  service whose `/v1/models` is empty cannot be added in the Cursor UI
  even though `/v1/chat/completions` would work. Source: forum #5.
- **Officially unsupported.** Cursor team has stated the override has
  "known limitations with certain providers." Source: forum #7.

## Test
See `tests/integrations/test_cursor.py` (Saturn-5pe, brutus). The test
should at minimum exercise:

- `saturn cursor-snippet` emits the five-step GUI walk-through with the
  Saturn endpoint substituted.
- The emitted base URL ends in `/v1` so Cursor's `/chat/completions` and
  `/models` suffixes resolve correctly.
- The snippet warns the user about Ask mode, HTTP/1.1, and subagents.

Run: `python3 -m pytest tests/integrations/test_cursor.py --cache-clear -v`
Last run: 2026-05-06, autonomous/promo-push, 9/9 PASSED.

| Scenario | Result | Duration | Notes |
|---|---|---|---|
| `test_cursor_subcommand_exists` | PASS | 0.08s | `saturn cursor-snippet` is registered. |
| `test_cursor_snippet_renders_base_url` | PASS | 0.05s | Emitted base URL ends in `/v1`. |
| `test_cursor_snippet_warns_ask_mode` | PASS | 0.06s | Snippet flags Agent vs Ask mode wire-format mismatch. |
| `test_cursor_snippet_warns_http2` | PASS | 0.06s | Snippet tells operator to flip Network → HTTP/1.1. |
| `test_cursor_snippet_describes_gui_flow` | PASS | 0.05s | Five-step Settings → Models walk-through emitted. |
| `test_cursor_snippet_warns_subagents` | PASS | 0.06s | Subagent fall-back-to-cloud caveat present. |
| `test_cursor_snippet_discovers_real_service` | PASS | 2.11s | Discovers a live `_saturn._tcp.local.` service and substitutes its endpoint. |
| `test_cursor_client_module_importable` | PASS | <0.01s | `saturn.clients.cursor` imports clean. |
| `test_cursor_doc_exists` | PASS | <0.01s | `docs/audit/cursor.md` present and non-empty. |
