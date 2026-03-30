# Brutus Bot

## User Story

I'm away from home — at a coffee shop, on campus, on my phone — and I want to use the LLM backends running on my home network. I open Discord, DM my private bot, and type a message. The bot replies like any chatbot. I never configure an endpoint, manage an API key, or think about mDNS. It just works.

## Problem Statement

Saturn solves zero-configuration discovery on a local network, but that locality is the constraint. Once you leave the LAN, you lose access to Saturn services entirely. Traditional solutions (VPN, port forwarding, public relay servers) add infrastructure, configuration, and cost — all things Saturn was designed to eliminate.

Discord provides a free, always-available, already-authenticated messaging channel between a user and a process running on their home network. A Discord bot running on a LAN device (a Raspberry Pi, an old PC) can bridge the gap: it receives messages from anywhere via Discord's gateway, discovers Saturn backends via mDNS locally, proxies the request, and returns the response as a Discord message. The user's experience is indistinguishable from talking to an LLM.

## Implementation

### Components

**Runtime**: Raspberry Pi 5 (Cortex-A76, 4GB RAM, 802.11ac WiFi, Gigabit Ethernet) or any always-on machine on the LAN. The workload (Discord gateway + HTTP proxy) is trivial for this hardware.

**Discord Bot** (`bot.py`): Private bot using discord.py. Listens for DMs only. On each message:

1. Discover available Saturn backends via mDNS (`_saturn._tcp.local.`)
2. Select the highest-priority healthy backend
3. Forward the message to `/v1/chat/completions`
4. Stream the response back as a Discord message

**Saturn Discovery**: Uses the existing zeroconf-based discovery from Saturn's client library. The bot maintains a cached, health-checked service list updated in the background, so discovery latency doesn't block individual messages.

**Conversation State**: The bot maintains a per-user conversation history (list of messages) in memory. Each DM appends to the history and sends the full context to the backend, enabling multi-turn conversation. History resets on bot restart or via a `/clear` command.

### Message Flow

```
User (anywhere)
  │
  │  Discord DM
  ▼
Discord Gateway (cloud)
  │
  │  WebSocket event
  ▼
Brutus Bot (Raspberry Pi, on LAN)
  │
  │  mDNS lookup (cached)
  ▼
Saturn Backend (on LAN)
  │
  │  /v1/chat/completions response
  ▼
Brutus Bot
  │
  │  Discord message reply
  ▼
User sees LLM response in Discord
```

### Streaming Strategy

Discord imposes a 2000-character message limit and rate limits on message edits (~5/5s). Options:

| Strategy | UX | Complexity |
|---|---|---|
| Wait for full response, send once | Slight delay, clean output | Low |
| Edit message as chunks arrive (~1 edit/sec) | Typing effect, feels live | Medium |
| Split long responses into multiple messages | No length limit, slight jank | Low |

Recommended: start with wait-and-send for simplicity. Add edit-based streaming later if the latency feels bad.

### Bot Commands

| Command | Action |
|---|---|
| (any message) | Send to LLM, reply with response |
| `/clear` | Reset conversation history |
| `/status` | List discovered Saturn services and their health |
| `/model <name>` | Pin to a specific model for subsequent messages |

### Auth Model

The bot is a private Discord application — not listed in any directory, not joinable via invite link. Only the bot owner (you) can DM it. Discord handles all authentication. No API keys, no tokens exposed, no public endpoints.

**Discord Permission Integer**: `3405594458537590`

## Discussion

### Why Discord

The key insight is that Discord solves three hard problems for free:
- **NAT traversal**: The bot opens an outbound WebSocket to Discord's gateway. No inbound ports, no public IP needed.
- **Authentication**: Discord's OAuth and DM permissions ensure only you can talk to the bot.
- **Client availability**: Discord runs on every platform — phone, laptop, browser, desktop. No custom client needed.

### Why This Matters for Saturn

Saturn's thesis is that AI access should be a network-level utility. Brutus extends that thesis beyond the LAN boundary without compromising the zero-configuration principle. The user's mental model stays the same: "I talk, I get a response." The infrastructure is invisible.

This also makes Saturn demonstrable to anyone — an advisor, a thesis committee member, a friend. "DM this bot" is a far more compelling demo than "install this library and run this script on the same network."

### Tradeoffs

- **Latency**: Discord adds ~100-300ms round-trip vs direct LAN access. Acceptable for chat.
- **Message limits**: 2000 chars per message. Long responses need splitting. Code blocks may get awkward.
- **Availability**: Depends on Discord's uptime (99.9%+) and the Pi being powered on and connected.
- **Privacy**: Messages transit Discord's servers. For a personal bot with personal LLM backends, this is fine. For sensitive enterprise use, it wouldn't be.

### Future Directions

- **Voice channel integration**: Discord voice + Whisper on a Saturn backend = voice-to-LLM.
- **Slash commands with parameters**: `/ask model:gpt-4 temperature:0.2 explain quantum tunneling`
- **Multi-user**: Invite trusted friends to a server with the bot. Saturn serves everyone on the network; now Discord extends that to friends off the network.
- **File attachments**: Send images/documents in the DM, bot forwards to multimodal endpoints.

## Research Findings

### llmcord Source Code Analysis

**Sources:**
- [llmcord repository](https://github.com/jakobdylanc/llmcord) — `llmcord.py` (~338 lines), `config-example.yaml`, `requirements.txt`

**Findings:**

*Architecture:* Single-file bot on `discord.py` (`commands.Bot`). Two event handlers: `on_ready()` (logs invite URL, syncs slash commands) and `on_message()` (the entire core — checks permissions, builds conversation chain, calls LLM, streams response). One slash command: `/model` for runtime model switching. Config hot-reloaded from YAML on every message.

*Conversation state:* Uses Discord's reply chain as conversation structure — no separate per-user history. A `MsgNode` dataclass caches message metadata, and the bot walks backward through `parent_msg` references to reconstruct context up to `max_messages` (default 25). Cache hard-capped at 500 nodes with LRU eviction. Each node has its own `asyncio.Lock`.

*LLM integration:* Uses the `openai` Python SDK (`AsyncOpenAI`). A new client is constructed per message (not pooled). Provider `base_url` and `api_key` come from YAML config. The `api_key` defaults to `"sk-no-key-required"` — matches Saturn's network-local model. Always uses `stream=True`.

*Dependencies:* `discord.py>=2.6.0`, `httpx`, `openai`, `pyyaml` — 4 packages total.

*Limitations:* Single global `curr_model` (all users share one model). No retry logic, no circuit breakers, no rate limit handling. Silent failure on API errors. New OpenAI client per message (not pooled). Config re-read from disk on every message.

**Recommendations:**
- Fork pattern, not dependency. Extract llmcord's message-chain-walking and streaming-embed patterns into Brutus.
- Adopt the reply-chain conversation model — it eliminates the need for a separate conversation store and gives free branching/persistence via Discord.
- Replace static YAML provider config with Saturn mDNS discovery. The adaptation point is exactly one line: `base_url = config["providers"][provider]["base_url"]` becomes `base_url = discovery.get_best_service().effective_endpoint`.
- Add per-user model selection (not global). Pool `AsyncOpenAI` clients per endpoint.

---

### llmcord Streaming & Discord Integration

**Sources:**
- [llmcord source](https://github.com/jakobdylanc/llmcord) — streaming loop (lines 247–314)
- [Discord API Rate Limits](https://docs.discord.com/developers/topics/rate-limits)
- [discord.py Intents Primer](https://discordpy.readthedocs.io/en/latest/intents.html)

**Findings:**

*Edit-based streaming:* `EDIT_DELAY_SECONDS = 1` (hardcoded). Bot checks `now - last_task_time >= 1s` before issuing an edit. A `⚪` suffix indicates in-progress content; removed on final edit. Embeds use orange (incomplete) / dark green (complete) color coding. When a forced edit is needed before cooldown, the bot sleeps the remainder: `await asyncio.sleep(1 - delta)`. The `last_task_time` is module-global — edit cooldown is shared across ALL channels (conservative but safe).

*Message splitting:* Embed mode uses 4096-char limit (not 2000). Split threshold is `4096 - len("⚪") = 4090` chars. Splits are purely character-count based — **no natural boundary splitting, no code fence tracking**. Subsequent messages reply to the previous bot message, creating a visual chain.

*Typing indicator:* The entire streaming loop runs inside `async with channel.typing():`. This covers initial LLM latency and auto-refreshes every ~9s. The maintainer explicitly rejected placeholder messages (issue #75) — typing indicator alone serves as the "thinking" signal.

*Rate limit handling:* The 1-second edit interval is the only mitigation. No retry, no backoff. discord.py's built-in HTTP-layer rate limit handling (automatic `Retry-After`) is the safety net.

*Partial failure:* `try/except Exception` wraps the streaming block. Partial content is preserved — user sees whatever streamed before the error. Embed stays orange. No error message sent to user. Node text is set to collected content regardless, so partial responses are cached for conversation continuity.

**Recommendations:**
- Use embeds (4096 chars) over plain messages (2000 chars) — fewer splits, better UX. Copy the color-coding pattern.
- Implement smart splitting: search backward from limit for `\n\n` > `\n` > space. Track open triple-backtick fences and close/reopen across splits.
- Add error notification on stream failure: append `"\n\n---\n*Response interrupted.*"` to partial content.
- Use per-channel edit timing instead of global — prevents concurrent conversations from throttling each other.
- For long initial latency (>5s with no tokens), send a brief "Thinking..." embed that gets edited with the actual response.

---

### Saturn/mDNS Adaptation

**Sources:**
- [llmcord source](https://github.com/jakobdylanc/llmcord) — provider config (lines 140–146)
- Saturn `discovery.py` — `SaturnDiscovery`, `SaturnService`, priority-based selection
- Saturn `mdns/userspace.py` — `UserspaceBackend` using threaded `ServiceBrowser`

**Findings:**

*Minimal integration point:* llmcord constructs a fresh `AsyncOpenAI(base_url=..., api_key=...)` per message. Swapping the endpoint is trivial — replace config lookup with `discovery.get_best_service()`. Saturn backends already expose `/v1/chat/completions`.

*Event loop compatibility:* Saturn's `SaturnDiscovery` is thread-based (`threading.Lock`, zeroconf's `ServiceBrowser` daemon thread). discord.py runs on asyncio. Since `get_best_service()` is a fast dict lookup under lock, it's safe to call from the asyncio thread directly. For caution: `await asyncio.to_thread(discovery.get_best_service)`. Do **not** rewrite to `AsyncZeroconf` for v1.

*Failover:* Since a fresh client is created per message, failover is natural — iterate `get_all_services()` (already priority-sorted) and try each:

```python
for service in discovery.get_all_services():
    if service.circuit_breaker.is_open:
        continue
    try:
        client = AsyncOpenAI(base_url=service.effective_endpoint,
                             api_key=service.ephemeral_key or "sk-no-key-required")
        async for chunk in await client.chat.completions.create(**kwargs):
            ...
        break
    except Exception:
        continue
```

*Health checking:* Add an asyncio background task polling `/v1/health` every 20s. Runs cleanly in discord.py's event loop. Filter `get_best_service()` to healthy backends only.

*Shutdown gotcha:* Do not call `discovery.stop()` from the asyncio thread — zeroconf's close blocks waiting for its thread to join. Use `atexit` or `on_close`.

**Recommendations:**
- Keep threaded zeroconf. `SaturnDiscovery` already works; call `get_best_service()` from discord.py handlers.
- Start health-check coroutine in `on_ready()`. Tag services healthy/unhealthy.
- Expose `/model` slash command listing models aggregated from all discovered services' `SaturnService.models`.
- Store per-user model selection (not global like llmcord).
- Bot lives at `discord/bot.py`. Dependencies: `discord.py>=2.6`, `openai`, `httpx`, `pyyaml`. Saturn's discovery is importable as `from saturn.discovery import SaturnDiscovery`.

---

### Raspberry Pi Deployment

**Sources:**
- [TeapotLLM Discord Bot](http://teapotai.com/blogs/teapotllm_discord_bot.html) (proves Pi-hosted LLM Discord bots work)
- [systemd service gist for Discord bots](https://gist.github.com/comhad/de830d6d1b7ae1f165b925492e79eac8)
- [discord.py reconnection (issue #1936)](https://github.com/Rapptz/discord.py/issues/1936)

**Findings:**
- A DM-only discord.py bot uses **30–80 MB RAM**. The Pi 5's 4GB is dramatically overpowered.
- discord.py handles gateway reconnection automatically (`reconnect=True` default). No custom reconnection logic needed. `on_disconnect()` and `on_resumed()` events are available for logging.
- systemd unit file essentials: `After=network-online.target`, `Restart=on-failure`, `RestartSec=10`, `StartLimitBurst=5`/`StartLimitIntervalSec=300` to prevent restart loops. Point `ExecStart` at the venv Python directly.
- Optional watchdog: `WatchdogSec=60` in the unit + `sdnotify` Python package to ping systemd every 30s. Catches deadlocks and event loop stalls.
- Token storage: `.env` file with `chmod 600`, referenced via `EnvironmentFile=` in the unit. Add `PYTHONUNBUFFERED=1` so logs appear in journald immediately.
- Use **uv** for dependency management (project already has `uv.lock`). ARM64 wheels exist for discord.py.
- Consider USB/NVMe boot instead of SD card for 24/7 operation to avoid SD wear.

**Recommendations:**
- Deploy as a systemd service with the watchdog. Log to journald (no log rotation needed).
- Do not write custom reconnection logic — discord.py + systemd together cover all failure modes.

---

### Traditional CS & AI Methods

**Sources:**
- RFC 7230 §5.7 (proxy/gateway taxonomy), RFC 5766 (TURN), RFC 6762/6763 (mDNS/DNS-SD)
- Gamma et al., *Design Patterns* (1994) — Proxy, Adapter patterns
- Hohpe & Woolf, *Enterprise Integration Patterns* (2003) — Request-Reply, Message Translator, Content Enricher
- Hintjens, *ZeroMQ* (2013) — Lazy Pirate pattern (Ch. 4: Reliable Request-Reply)
- Nygard, *Release It!* 2nd ed. (2018) — Circuit Breaker, Bulkhead, Timeout patterns
- AWS Architecture Blog, "Exponential Backoff and Jitter" (Brooker, 2015)
- [Fowler, "Gateway" pattern article](https://martinfowler.com/articles/gateway-pattern.html)

**Findings:**

*Proxy taxonomy:* Brutus is an **application gateway with protocol translation** (RFC 7230 §5.7). It composes two GoF patterns: **Adapter** (translates Discord WS events ↔ OpenAI HTTP — different interfaces) and **Proxy** (surrogate for LLM backends with added service discovery, auth, and history). Fowler's Gateway pattern refines this: a Gateway wraps a "foreign" API with a convenient local API. Brutus defines a "DM me and I reply" interface that wraps the OpenAI API.

*NAT traversal:* Discord's gateway is functionally a **TURN relay** (RFC 5766) with persistent WebSocket connections. The same "outbound-persistent-connection" principle is used by MQTT (IoT) and mobile push (APNs/FCM). The tradeoff is sovereignty — you depend on Discord's uptime and ToS.

*Service discovery taxonomy:* Three categories exist — zero-config/mDNS (Bonjour, Avahi, Saturn), CP-consistent (Consul, etcd, ZooKeeper), AP-available (Eureka, Nacos). Saturn occupies zero-config: client-side discovery, no central registry, no single point of failure, no consistency protocol. The tradeoff (two clients may momentarily disagree on available services) is acceptable for LLM routing. Consul/etcd solve a different problem (cross-datacenter, strongly consistent) and require server infrastructure contradicting Saturn's thesis.

*Message patterns:* Request-Reply (user DM → LLM response, correlated by channel ID), Content Enricher (attaching conversation history before forwarding), and Message Translator (bidirectional: Discord `MESSAGE_CREATE` → `ChatCompletionRequest`; SSE stream → Discord embed edits).

*Failover — Lazy Pirate with ordered failover:* The basic Lazy Pirate (Hintjens Ch. 4) retries the same server. Brutus extends it: try each backend once in priority order, with circuit breakers preventing retries to known-dead backends. This maps to Hintjens' progression from Lazy Pirate → Simple Pirate (load-balancing queue) → Paranoid Pirate (heartbeating). Saturn's `/v1/health` polling is the Paranoid Pirate's heartbeat.

*Resilience:* Per-backend **circuit breakers** (closed → open after 3 failures → half-open probe after 30s). **Layered timeouts** for LLM streaming:

| Timeout | Value | Rationale |
|---|---|---|
| TCP connect | 5s | Backend on LAN; catches dead hosts |
| First byte (TTFT) | 30s | Covers model loading, queue wait |
| Inter-chunk idle | 10–15s | Detects mid-stream stalls |
| Total request | 120–180s | Hard ceiling for long generations |

**Backoff with full jitter**: `sleep = random.uniform(0, min(cap, base * 2^attempt))` (AWS/Brooker). For single-user bot, jitter matters less but costs nothing to implement correctly.

*Conversation state:* Classical two-level bounding — LRU across users (`OrderedDict`, max ~100) and sliding window per user (`deque(maxlen=50)`). Token-budget trimming (heuristic: 1 token ≈ 4 chars) before dispatch for context window compliance. Research shows LLMs perform worse in very long multi-turn conversations, so aggressive trimming can improve response quality.

*Event deduplication:* Discord may redeliver events on reconnection. Maintain a bounded set of recently-seen message IDs (~1000 entries, pruned by age).

**Recommendations:**
- Frame Brutus in the thesis as an "application gateway with protocol translation using a hosted TURN-equivalent relay" — places it in 30+ years of established taxonomy.
- Describe failover as "Lazy Pirate with ordered failover" (Hintjens terminology). Circuit breakers are the natural extension (Paranoid Pirate's heartbeating = Saturn's health polling).
- Implement per-backend circuit breakers (~50 lines). Use layered `httpx` timeouts. A simple for-loop over priority-sorted backends with breaker checks is cleaner than `tenacity`'s decorator approach.
- Start with `deque(maxlen=50)` for conversation state. Token-budget trimming is v2.
- Deduplicate incoming Discord events by message ID.

---

### Pattern Summary

| Component | Pattern | Source | Implementation |
|---|---|---|---|
| Bot architecture | Application Gateway + Adapter | RFC 7230, GoF (1994) | Protocol translation: Discord WS ↔ HTTP |
| Reference impl | llmcord fork | jakobdylanc/llmcord | Extract message-chain + streaming-embed patterns |
| Service discovery | Client-side mDNS, priority sort | RFC 6762/6763 | Saturn's `SaturnDiscovery` class |
| Message flow | Request-Reply + Content Enricher + Message Translator | Hohpe & Woolf (2003) | Enrich with history, translate protocols |
| Failover | Lazy Pirate with ordered failover | Hintjens (2013) | For-loop over priority-sorted backends |
| Resilience | Circuit Breaker + layered Timeouts | Nygard (2018) | Per-backend breaker, 5s/30s/15s/120s timeouts |
| Backoff | Full Jitter exponential backoff | AWS/Brooker (2015) | `random.uniform(0, min(cap, base * 2^n))` |
| Conversation state | Bounded deque + optional token budget | Classical LRU / sliding window | `deque(maxlen=50)` per user |
| Streaming UX | Embed edits at 1s interval | llmcord (proven) | Color-coded embeds, smart splitting |
| Dependencies | Minimal (4 packages) | llmcord pattern | `discord.py`, `openai`, `httpx`, `pyyaml` |
