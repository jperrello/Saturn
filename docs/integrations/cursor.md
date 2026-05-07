# Cursor IDE + Saturn

Cursor's "Override OpenAI Base URL" is configured exclusively through the IDE
GUI. There is no public `settings.json` key for it, no `~/.cursor/cli-config.json`
entry, and no `mcp.json` shortcut — verified against current Cursor builds and
community research (see `dist/research/cursor_config.md` by gullivan2).

Saturn ships a helper that prints the walkthrough with a resolved endpoint:

```
saturn cursor-snippet                            # auto-discover via mDNS
saturn cursor-snippet --base-url http://x:8080/v1
```

## Walkthrough

1. **Open Cursor → Settings (Cmd/Ctrl + ,)**.
2. Go to **Settings > Models**.
3. In the OpenAI API Key section, click **Override OpenAI Base URL** and paste
   the Saturn endpoint (e.g. `http://saturn.local:8080/v1`).
4. Paste any non-empty API key (Cursor does not validate it locally; it just
   attaches the value as the `Authorization: Bearer …` header). `saturn-dummy`
   works fine.
5. Click **Add Model** and enter the model id you want exposed.

## Required: Ask mode, not Agent mode

Cursor's Agent mode emits Responses-API-shaped payloads against
`/chat/completions`, which breaks against any pure Chat-Completions endpoint —
Saturn included. **Use Ask mode** for Saturn-routed traffic. Toggle Ask / Agent
in the chat composer.

## Required: HTTP/1.1, not HTTP/2

Cursor's custom-OpenAI client is incompatible with HTTP/2 upstreams. Flip:

```
Settings > Network > HTTP Compatibility Mode -> HTTP/1.1
```

HTTP/2 is not supported in this code path. Saturn's own server speaks HTTP/1.1
already; this toggle is purely for Cursor's internal client.

## Caveat: subagents bypass the override

Subagent and background-task calls in Cursor bypass the `Override OpenAI Base
URL` setting and go straight to Cursor's hosted backend. **Only the main
Ask-mode pane routes through Saturn.** If you need every call routed (including
subagents), put the wrapping upstream of Cursor entirely (e.g. an HTTP proxy on
localhost) rather than relying on the per-model override.

## References

- Research: `dist/research/cursor_config.md` (gullivan2)
- CLI source: `saturn/clients/cursor.py`
- Discover endpoints: `saturn discover --json`, `saturn endpoint`
