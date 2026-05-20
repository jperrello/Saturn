# Fallback

Saturn-shipped sentinel server. Exists to exercise discovery, priority
sorting, and failover logic — not to serve real model output.

## Status
TBD (works | bit-rotted | broken)

## 2026-verified install

Source: `saturn/servers/fallback.py`. Service definition:
`saturn/services/fallback.toml`.

```toml
# saturn/services/fallback.toml
name       = "fallback"
deployment = "network"
api_type   = "openai"
priority   = 99

[upstream]
base_url = ""

[server]
port   = 0
module = "saturn.servers.fallback"

[beacon]
enabled = false
```

No upstream. Self-contained — only Python stdlib and FastAPI.

## How it points at Saturn

The Saturn launcher reads `fallback.toml`, starts the FastAPI app at
`saturn/servers/fallback.py:13` on an auto-allocated port, and advertises
under `_saturn._tcp.local.` with `priority=99` (deliberately the highest
numeric priority — i.e. lowest preference; the sort order at every Saturn
client puts this server last).

Endpoints exposed (`saturn/servers/fallback.py:31, :36, :41`):

| Path | Method | Behaviour |
|---|---|---|
| `/v1/health` | GET | `{ "status": "ok", "provider": "Fallback", "saturn": true }`. |
| `/v1/models` | GET | Returns a single model `id="dont_pick_me"`. |
| `/v1/chat/completions` | POST | If `model != "dont_pick_me"`, returns 400. Otherwise responds with one of eight canned roast lines (`saturn/servers/fallback.py:19–28`); supports streaming. |

The model name is the test contract: a discovery client that lands on
`dont_pick_me` has selected the wrong service. The eight canned responses
are diagnostics, not content.

## Known issues

- **Not for production use.** This is a test fixture that ships in the
  Saturn distribution. Operators running a public Saturn beacon should
  disable the fallback service in their config; a consumer that lands on
  `priority=99` because every higher-preference service is unhealthy will
  receive nonsense output and a 400 for any model name except
  `dont_pick_me`.
- **Single deterministic model name.** `dont_pick_me` is hard-coded
  (`saturn/servers/fallback.py:38, :43`). Tests that drive it must use
  exactly that string.

## Test
See `tests/integrations/test_fallback.py`.

<!-- bombadil: results table goes here -->

| Scenario | Result | Notes |
|---|---|---|
| TBD | TBD | TBD |
