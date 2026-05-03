# Web UI screenshots

Captured against `saturn web --port 3030` with a local `saturn run ollama`
proxy advertised on the same network. Browser unlocked with the default
admin password (`saturn`). All shots are 1400×900 from headless Chrome
via `rodney`.

- **`01-discover.png`** — *Network Scan* tab. Left pane shows the
  Saturn 3D scene; right pane shows the discovered service
  `ollama-8080` (status online) and the configured-services list with
  start/stop controls.
- **`02-chat.png`** — *Chat* tab past the experimental-feature gate.
  Service and model selectors at the top (`⊙ ollama-8080` /
  `qwen2.5:0.5b`), the chat shell with the initial "How can I help
  today?" prompt, and a sample user message in the input bar.
- **`03-system-status.png`** — *System → Status* sub-tab. Universe
  Health lists `ollama-8080 [ok]`; Routing Activity and Usage Today
  panels are empty because no proxied requests have been made yet
  through the Web UI.
- **`04-system-integrate.png`** — *System → Integrate* sub-tab. Cards
  for OpenCode, Codex, Continue, Aider, Cline, Cursor, Claude Code,
  OpenClaw, Generic — the supported integrations for pointing
  third-party tools at a Saturn-discovered backend.

## Re-shoot

```sh
saturn web --port 3030 &
saturn run ollama &
rodney start
rodney open http://127.0.0.1:3030/
# unlock admin
rodney input '#admin-pw' saturn && rodney click '#admin-pw-submit'
# 01 discover
rodney click '#discover-btn' && rodney sleep 6
rodney screenshot -w 1400 -h 900 demo/screenshots/01-discover.png
# 02 chat
rodney click '[data-tab=chat]' && rodney click '#chat-accept'
rodney input '#chat-input' 'What can Saturn discover on this network?'
rodney screenshot -w 1400 -h 900 demo/screenshots/02-chat.png
# 03 system status
rodney click '[data-tab=system]' && rodney click '[data-subtab=status]'
rodney screenshot -w 1400 -h 900 demo/screenshots/03-system-status.png
# 04 system integrate
rodney click '[data-subtab=integrate]'
rodney screenshot -w 1400 -h 900 demo/screenshots/04-system-integrate.png
```
