# Saturn Servers

Saturn servers expose AI backends via mDNS service discovery. Each server advertises itself as `_saturn._tcp.local.` and provides an OpenAI-compatible API.

## Quick Reference

| Server | Use Case | Requirements | Default Priority |
|--------|----------|--------------|------------------|
| Fallback | Testing, learning | None | 999 |
| Ollama | Free, private, offline | Local Ollama install | 10 |
| OpenRouter | 200+ cloud models | API key | 50 |

**Lower priority = higher preference.** Clients select the lowest-priority healthy service.

---

## Fallback Server

The world's most honest server. Model literally named "dont_pick_me". If you actually pick it, it roasts you.

**When to use:**
- Testing client discovery
- Learning how Saturn works
- Verifying network setup

**Run:**
```bash
python servers/fallback_server.py --priority 999
```

**Verify:**
```bash
curl http://localhost:8080/v1/health
```

---

## Ollama Server

Connects to your local Ollama installation. Zero external API costs.

**When to use:**
- Free, private AI
- Offline capability
- You have the hardware

**Prerequisites:**
1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3`
3. Verify Ollama is running: `ollama list`

**Run:**
```bash
python servers/ollama_server.py --priority 10
```

**Features:**
- Auto-discovers installed models
- Converts Ollama format to OpenAI-compatible
- Full streaming support

**Verify:**
```bash
curl http://localhost:8080/v1/models
```

---

## OpenRouter Server

Proxies to OpenRouter API for access to 200+ models (Claude, GPT-4, Gemini, Llama, etc.).

**When to use:**
- Need cutting-edge models
- Want variety
- Okay with API costs

**Prerequisites:**
1. Get API key: https://openrouter.ai/keys
2. Create `.env`:
```bash
echo "OPENROUTER_API_KEY=your-key-here" > .env
echo "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions" >> .env
```

**Run:**
```bash
python servers/openrouter_server.py --priority 50
```

**Features:**
- Fetches and caches models (1-hour TTL)
- Includes `openrouter/auto` for intelligent routing
- Full streaming support

**Verify:**
```bash
curl http://localhost:8080/v1/health
```

---

## CLI Arguments

All servers accept:

```
--host <ip>       # Default: 0.0.0.0
--port <port>     # Default: auto-find starting at 8080
--priority <num>  # Default: 50
```

**Example:**
```bash
python servers/openrouter_server.py --host 192.168.1.100 --port 8081 --priority 5
```

## Port Auto-Discovery

If you don't specify a port, Saturn finds an available one:
- Tries 8080, 8081, 8082... up to 8099
- Uses first available
- No port conflicts

---

## Custom Servers

Create your own by following the pattern in this directory. Announce via:

```bash
dns-sd -R "MyServer" "_saturn._tcp" "local" 8081 "version=1.0" "api=custom" "priority=50"
```

Required endpoints:
- `GET /v1/health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat (streaming supported)

---

## Troubleshooting

**Server not discovered:**
```bash
# Verify mDNS is working
dns-sd -B _saturn._tcp local.
```

**Port in use:**
```bash
# Let Saturn auto-find a port
python servers/openrouter_server.py  # Omit --port
```
