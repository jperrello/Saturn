# Web UI screenshots

Captured against `saturn web --port 3030` (commit `c4610a6`+) with a
local `saturn ollama` proxy advertised on the same network. Browser
unlocked with the default admin password (`saturn`). All shots are
1400×900 from a headless Chrome via `rodney`.

- **`01-discover.png`** — *Network Scan* tab. Left pane shows the
  Saturn 3D scene; right pane shows the discovered service
  `ollama-8080 @ joeyair.local:8080` (status online, priority 50)
  and the configured-services list with start/stop controls.
- **`02-chat.png`** — *Chat* tab past the experimental-feature gate.
  Service and model selectors at the top, the chat shell with the
  initial "How can I help today?" prompt, and a user message typed
  into the input bar ready to send.
- **`03-system-status.png`** — *System → Status* sub-tab. Universe
  Health lists `ollama-8080 [ok]`; Routing Activity and Usage Today
  panels are empty because no proxied requests have been made yet
  through the Web UI.
- **`04-system-integrate.png`** — *System → Integrate* sub-tab. Cards
  for OpenCode, Codex, Continue, Aider, Cline, Cursor, Claude Code,
  OpenClaw, Generic — the supported integrations for pointing
  third-party tools at a Saturn-discovered backend.

## Caveats and known issues

- The Discover tab's `#discover-btn` click handler (Web-UI/app.js:870)
  hangs on `syncServices()` due to a `serviceSelect` TDZ error after
  the hardener's ES-module migration. Worked around for the screenshot
  by injecting the `/api/discover` JSON straight into the
  `#services-list` DOM. The service shown is real, the rendering path
  is the production CSS, but the click-driven flow needs a follow-up
  fix. (See bd `Saturn-kul` thread.)
- The chat experimental-feature gate (`#chat-accept` button in
  `Web-UI/index.html:253`) has no JS handler bound, so it can't be
  dismissed by clicking. Shot taken after manually hiding `#chat-gate`
  and removing `hidden` from `#chat-shell`.
- The System sub-tab buttons (`[data-subtab=...]`) also don't switch
  panels via click; activated manually for `03` and `04`.

## Re-shoot

```sh
saturn web --port 3030 &
saturn ollama &
rodney start
rodney open http://127.0.0.1:3030/
# unlock with default password 'saturn' (or set SATURN_ADMIN_PASSWORD)
# until the click-handler bugs above are fixed, use the JS workarounds
# documented in this file.
```
