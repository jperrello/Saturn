# HTTP API

Two distinct surfaces ship under the same TCP port. Don't confuse them.

| Surface | Routes | Audience | Stability |
|---|---|---|---|
| **Saturn protocol** | `/v1/health`, `/v1/models`, `/v1/chat/completions` | Any conformant Saturn client | **Normative** — required for protocol conformance |
| Reference Python Web-UI | `/api/*` (services, discover, brutus, mcp, admin, …) | The bundled Web-UI in `saturn-ai` | Implementation-specific; not part of the protocol |

A non-Python implementation MUST serve the three protocol routes and MAY ignore the Web-UI routes entirely.

---

## Saturn protocol — `/v1/*`

The contract every Saturn responder MUST honor. OpenAI-compatible by design — drop the discovered URL into any tool that accepts a `base_url`.

### `GET /v1/health`

Liveness probe. Source: `saturn/web.py:705-707`.

```bash
$ curl http://macbook.local:11434/v1/health
{"status":"ok"}
```

`200 OK` indicates the responder is up and willing to serve `/v1/models` and `/v1/chat/completions`. Browsers SHOULD probe this before routing the first request and use the result as the failover signal.

> **Doc-drift note.** Earlier docs and Saturn.md:531–532 cite `/health`. The deployed reference implementation serves `/v1/health`; treat `/health` as historical and prefer the `/v1/`-prefixed path.

### `GET /v1/models`

Returns the list of models the responder can serve. Body matches the [OpenAI model-list shape](https://platform.openai.com/docs/api-reference/models/list).

```bash
$ curl http://macbook.local:11434/v1/models
{"object":"list","data":[
  {"id":"llama3.2","object":"model","owned_by":"ollama"},
  {"id":"qwen2.5","object":"model","owned_by":"ollama"}
]}
```

For cloud responders advertising `deployment=cloud`, send the `ephemeral_key` from TXT as `Authorization: Bearer <key>`.

### `POST /v1/chat/completions`

Chat completion. Body and response follow the [OpenAI chat-completions shape](https://platform.openai.com/docs/api-reference/chat). Streaming via Server-Sent Events when `stream: true`.

```bash
$ curl http://macbook.local:11434/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "llama3.2",
      "messages": [{"role":"user","content":"hi"}],
      "stream": false
    }'
{"id":"chatcmpl-...","choices":[{"message":{"role":"assistant","content":"Hello!"}}], ...}
```

Streaming response (`stream: true`):

```
data: {"id":"...","choices":[{"delta":{"content":"Hel"}}]}

data: {"id":"...","choices":[{"delta":{"content":"lo!"}}]}

data: [DONE]
```

Standard sampling parameters (`temperature`, `max_tokens`, `top_p`, `top_k`, `frequency_penalty`, `presence_penalty`, `seed`, `stop`) pass through unchanged. Backend-specific parameters (Ollama: `num_ctx`, `keep_alive`, `mirostat*`, `tfs_z`; Anthropic: `thinking`) pass through to the upstream when the responder's `api_type` matches.

### Authentication on protocol routes

When the responder advertises `deployment=cloud`, send the TXT `ephemeral_key` as a Bearer token:

```bash
$ curl https://openrouter.ai/api/v1/chat/completions \
    -H "Authorization: Bearer $EPHEMERAL_KEY" \
    -H "Content-Type: application/json" \
    -d '{...}'
```

For `deployment=local` and `deployment=network`, no auth is required at the protocol layer — the LAN is the trust boundary. Operators who need stronger guarantees front Saturn with a TLS-terminating reverse proxy and gate it with `SATURN_RUNNER_TOKEN`. → [Security model](security.md)

---

## Reference Python Web-UI — `/api/*`

The bundled Web-UI in `saturn-ai` exposes a REST surface on port 3000 (default) for service management, the chat UI, MCP integration, tunnels, and admin operations. **None of this is part of the Saturn protocol.** Other implementations are free to expose the same operations on different routes (or not at all).

### Authentication

Per CONFIG_FIELDS §A.2, every `/api/*` route except the small public set requires:

```
Authorization: Bearer $SATURN_ADMIN_TOKEN
```

`SATURN_ADMIN_TOKEN` has no default; Saturn refuses to start without it. The Web-UI form login (`POST /api/admin/auth`) takes the human-typed `SATURN_ADMIN_PASSWORD` and exchanges it for a signed session cookie (default 8 h TTL) — separate surface from the bearer token. → [Environment variables](../../configuration/env-vars.md)

### Services

| Route | Purpose |
|---|---|
| `GET /api/services` | List configured services with runtime status (`pid`, `port`, `mdns_name`). |
| `POST /api/services` | Create a service config. Body: `name`, `deployment`, `api_type`, optional `priority`, `base_url`, `api_key_env`, `port`, `beacon_*`, `rotation_interval`, `expiration_interval`. |
| `POST /api/services/{name}/start` | Start a service. May override `host` and `port` in body. |
| `POST /api/services/{name}/stop` | Stop a service. SIGTERM, 3 s wait. |
| `DELETE /api/services/{name}` | Delete a user-created service. Refuses built-in or running services. |

### Discovery and models

| Route | Purpose |
|---|---|
| `GET /api/discover` | Run mDNS discovery (5 s timeout, 1 s settle). Returns the same shape as a fresh `dns-sd -B` + resolve. |
| `GET /api/models/all` | Aggregate models across discovered, configured, and cloud services. Applies admin model filter. |
| `GET /api/models?service={name}` | Models from a single named service. |
| `GET /api/proxy/models?base_url={url}` | List models on an arbitrary upstream. **Do not pass `api_key` in the URL** — send `Authorization: Bearer <token>` on the request and Saturn forwards it (SECURITY_AUDIT.md §12.7, §11.4). |

### Chat completions (Web-UI surface)

| Route | Purpose |
|---|---|
| `POST /api/chat` | Chat completion through a named Saturn service. Rate-limited per client IP. |
| `POST /api/proxy/chat` | Chat completion against an arbitrary upstream. Body: `base_url`, `api_type`, plus the standard chat fields. **No `api_key` body field** — register the upstream as a Saturn service (with `api_key_env`) or send `Authorization: Bearer <token>` on the request (SECURITY_AUDIT.md §11.4, §11.8). |
| `POST /api/brutus/chat` | Auto-routed chat with circuit-breaker failover. Returns `X-Brutus-Service`, `X-Brutus-Model`, `X-Brutus-Skipped`, `X-Brutus-Latency` headers. |

`/api/chat` accepts the standard OpenAI sampling fields and the backend-specific fields documented in the protocol section above. `X-Saturn-Tokens-Remaining` reports the per-IP TPM budget; `X-Saturn-Resolved-Config` reports the config Saturn actually applied (token cap, temperature, model, system prompt) — visible-receipt-of-applied-settings is intentional UX (RUN_BRIEF_MAY04 Bucket 3c).

### Brutus (auto-routing)

| Route | Purpose |
|---|---|
| `GET /api/brutus/status` | Backend states (failures, open/closed circuit, cooldown), tunnel status, last 20 routing log entries. |
| `GET /api/brutus/url` | Public URL for this Saturn instance (tunnel URL if active, else LAN IP). Returns `{"url": "...", "mode": "tunnel"|"lan"}`. |

### Tunnels (Cloudflare)

| Route | Purpose |
|---|---|
| `GET /api/brutus/tunnel/status` | `running`/`stopped` + URL. |
| `POST /api/brutus/tunnel/start` | Start `cloudflared tunnel --url http://localhost:3000`. Waits up to 30 s for DNS propagation. |
| `POST /api/brutus/tunnel/stop` | Stop the tunnel. |

All three require `Authorization: Bearer $SATURN_ADMIN_TOKEN`. → [Tunnels guide](../../configuration/tunnels.md)

### MCP integration

| Route | Purpose |
|---|---|
| `GET /api/mcp/servers` | List configured MCP servers. |
| `POST /api/mcp/servers` | Add an MCP server. Body: `url`, optional `name`, `auth_token`. |
| `DELETE /api/mcp/servers/{name}` | Remove. |
| `GET /api/mcp/tools` | List tools across all configured MCP servers. |
| `POST /api/mcp/tools/call` | Body: `server`, `tool`, optional `arguments`. |

### Rate limiting

| Route | Purpose |
|---|---|
| `GET /api/rate-limit/status` | Current per-IP rate-limit state: `rpm`, `tpm`, `concurrent`, `global_concurrent`. |

### Usage tracking

| Route | Purpose |
|---|---|
| `GET /api/usage` | Today's token totals. The `user_id` query parameter is **admin-only** (was a query bypass — `SECURITY_AUDIT.md §9`); without admin auth, returns the caller's own totals only. |
| `POST /api/usage/report` | Record token usage for the calling IP. Body: `tokens_in`, `tokens_out`. |
| `GET /api/usage/history` | Historical usage. `user_id` admin-only; `days` defaults to 7. |

> Saturn keeps a small daily counter of how many tokens each LAN peer consumes through it — not what they asked or what came back, just totals. Per-peer queries require `SATURN_ADMIN_TOKEN`; the chat UI shows each user their own running session total. (`SECURITY_AUDIT.md §9.7`)

### Admin

| Route | Purpose |
|---|---|
| `POST /api/admin/auth` | Exchange `SATURN_ADMIN_PASSWORD` for a signed session cookie. Returns `{"ok": true}` on success, 401 on failure. |
| `GET /api/admin/config` | Current admin configuration (model filter, budgets, `trusted_proxies`, etc.). |
| `POST /api/admin/config` | Update admin configuration. Schema: CONFIG_FIELDS §A. |

→ [Wire format](wire-format.md) · [Discovery flow](discovery.md) · [Beacons](beacons.md) · [Security model](security.md) · [Environment variables](../../configuration/env-vars.md)
