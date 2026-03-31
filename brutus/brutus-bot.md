# Brutus Bot

## User Story

I'm away from home — at a coffee shop, on campus, on my phone — and I want to use the LLM backends running on my home network. I open Discord, DM my private bot, and type a message. The bot replies like any chatbot. I never configure an endpoint, manage an API key, or think about mDNS. It just works.

## Problem Statement

Saturn solves zero-configuration discovery on a local network, but that locality is the constraint. Once you leave the LAN, you lose access to Saturn services entirely. Traditional solutions (VPN, port forwarding, public relay servers) add infrastructure, configuration, and cost — all things Saturn was designed to eliminate.

Discord provides a free, always-available, already-authenticated messaging channel between a user and a process running on their home network. A Discord bot running on a LAN device (a Raspberry Pi, an old PC) can bridge the gap: it receives messages from anywhere via Discord's gateway, discovers Saturn backends via mDNS locally, proxies the request, and returns the response as a Discord message. The user's experience is indistinguishable from talking to an LLM.

## Implementation

### Two Interfaces, One Gateway

Brutus exists in two forms: a **Discord bot** (the original design) and a **Web UI tab** (the current implementation). Both are application gateways with protocol translation [RFC 7230 §5.7] — they compose the GoF Adapter pattern (translating Discord WS events or browser HTTP ↔ OpenAI HTTP) with the Proxy pattern (surrogate for LLM backends with service discovery, auth, and history) [Gamma et al., *Design Patterns*, 1994]. Fowler's Gateway pattern refines this: a Gateway wraps a "foreign" API with a convenient local API [Fowler, "Gateway" pattern article, martinfowler.com].

The Web UI tab (`saturn/web.py`, `/api/brutus/*` endpoints) implements the same priority-sorted failover with circuit breakers that the Discord bot spec describes, but replaces Discord's gateway with cloudflared tunnels for NAT traversal. Both approaches use an "outbound-persistent-connection" relay functionally equivalent to a TURN relay [RFC 5766] — Discord via WebSocket, cloudflared via QUIC tunnel.

### Components

**Runtime**: Raspberry Pi 5 (Cortex-A76, 4GB RAM, 802.11ac WiFi, Gigabit Ethernet) or any always-on machine on the LAN. The workload (Discord gateway + HTTP proxy) is trivial for this hardware.

**Discord Bot** (`bot.py`): Private bot using discord.py. Listens for DMs only. On each message:

1. Discover available Saturn backends via mDNS (`_saturn._tcp.local.`)
2. Select the highest-priority healthy backend
3. Forward the message to `/v1/chat/completions`
4. Stream the response back as a Discord message

**Web UI Tab** (`Web-UI/index.html`, Brutus section): Browser-based chat interface that:

1. Gathers candidates from discovered + running configured services
2. Sorts by priority, filters by circuit breaker state
3. Auto-selects the first model from the best available backend
4. Streams the response with `X-Brutus-Service` and `X-Brutus-Model` response headers
5. Syncs conversation history into the Chat tab

**Saturn Discovery**: Uses the existing zeroconf-based discovery from Saturn's client library. The bot maintains a cached, health-checked service list updated in the background, so discovery latency doesn't block individual messages.

**Conversation State**: Both interfaces maintain per-user conversation history in memory. Each message appends to the history and sends the full context to the backend, enabling multi-turn conversation. History resets on restart or via a clear action. This is a classical two-level bounding pattern — LRU across users (`OrderedDict`, max ~100) and sliding window per user (`deque(maxlen=50)`) [Hohpe & Woolf, *Enterprise Integration Patterns*, 2003].

### Message Flow

```
User (anywhere)
  │
  │  Discord DM  /  HTTPS via cloudflared tunnel
  ▼
Discord Gateway (cloud)  /  Cloudflare edge
  │
  │  WebSocket event  /  HTTP request
  ▼
Brutus Bot  /  Saturn Web Backend (on LAN)
  │
  │  mDNS lookup (cached), priority-sorted failover
  ▼
Saturn Backend (on LAN)
  │
  │  /v1/chat/completions response
  ▼
Brutus Bot  /  Saturn Web Backend
  │
  │  Discord message reply  /  SSE stream
  ▼
User sees LLM response
```

This flow implements three message patterns from Hohpe & Woolf [*Enterprise Integration Patterns*, 2003]: Request-Reply (user message → LLM response, correlated by channel/session ID), Content Enricher (attaching conversation history before forwarding), and Message Translator (bidirectional protocol conversion).

### Streaming Strategy

Discord imposes a 2000-character message limit and rate limits on message edits (~5/5s). Options:

| Strategy | UX | Complexity |
|---|---|---|
| Wait for full response, send once | Slight delay, clean output | Low |
| Edit message as chunks arrive (~1 edit/sec) | Typing effect, feels live | Medium |
| Split long responses into multiple messages | No length limit, slight jank | Low |

Recommended: start with wait-and-send for simplicity. Add edit-based streaming later if the latency feels bad.

The Web UI tab already implements streaming — tokens arrive via SSE and render incrementally with a blinking cursor. llmcord's approach [jakobdylanc/llmcord, lines 247–314] uses embeds (4096-char limit, fewer splits) with color-coded state (orange = incomplete, dark green = complete) and a 1-second edit cooldown. The Web UI should adopt the color-coding pattern for its streaming indicator.

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

### Failover & Resilience

Failover follows the **Lazy Pirate with ordered failover** pattern [Hintjens, *ZeroMQ*, 2013, Ch. 4]. The basic Lazy Pirate retries the same server; Brutus extends it by trying each backend once in priority order, with per-backend **circuit breakers** preventing retries to known-dead backends [Nygard, *Release It!* 2nd ed., 2018]. Saturn's `/v1/health` polling is the Paranoid Pirate's heartbeat — the natural extension of Hintjens' progression from Lazy Pirate → Simple Pirate → Paranoid Pirate.

Circuit breaker states: closed → open after 3 failures → half-open probe after 30s. Current implementation in `web.py` (`_breakers` dict, `BREAKER_THRESHOLD = 3`, `BREAKER_COOLDOWN = 30`).

**Layered timeouts** for LLM streaming:

| Timeout | Value | Rationale |
|---|---|---|
| TCP connect | 5s | Backend on LAN; catches dead hosts |
| First byte (TTFT) | 30s | Covers model loading, queue wait |
| Inter-chunk idle | 10–15s | Detects mid-stream stalls |
| Total request | 120–180s | Hard ceiling for long generations |

**Backoff with full jitter**: `sleep = random.uniform(0, min(cap, base * 2^attempt))` [Brooker, "Exponential Backoff and Jitter," AWS Architecture Blog, 2015].

## Web UI: Communicating What Brutus Is Doing

The core challenge for the Brutus UI is Nielsen's first usability heuristic: **Visibility of System Status** — "the design should always keep users informed about what is going on, through appropriate feedback within a reasonable amount of time" [Nielsen, "10 Usability Heuristics," 1994; Nielsen & Molich, *Proc. ACM CHI'90*, 1990]. When Brutus acts as an opaque proxy, the user cannot answer basic questions: Which backend handled my message? Is the system healthy? Did failover just happen? This is Don Norman's **Gulf of Evaluation** — the difficulty a user faces in determining whether the system has reached the desired state [Norman, *The Design of Everyday Things*, 1988/2013, ch. 2].

The current Web UI (`Web-UI/index.html`, Brutus section) has five UI gaps:

1. **Routing is opaque** — user sees "routing..." then the selected service, with no visibility into *why* that backend was chosen
2. **Circuit breaker state is invisible** — no indication which backends are degraded or tripped
3. **No latency/performance feedback** — no tokens/sec, no time-to-first-token
4. **Backend list is static** — the sidebar shows discovered services but doesn't poll health in real-time
5. **Failover is silent** — if backend A fails and Brutus falls through to backend B, nothing tells the user

### Design Principles

Three principles from the research literature guide the solution:

**Progressive Disclosure** [Nielsen, NNGroup, 2006; Shneiderman, *Designing the User Interface*, 1987]: Show the most important information first; provide details on demand. Three levels:
- **Level 1 (always visible):** Colored dot + backend name. "Connected · saturn-lab". ~50px.
- **Level 2 (on click):** Expanded details — priority, model, latency, all discovered services with health.
- **Level 3 (on demand):** Full diagnostic — routing log, health check history, circuit breaker states.

**Information Radiator** [Cockburn, *Agile Software Development*, 2002]: A glanceable, ambient display that passively radiates system state. Key properties: understood in <1 second, always available, real-time updated. A row of colored dots (one per discovered service) functions as an information radiator for backend health.

**Informative Feedback** [Shneiderman's Rule 3]: For frequent actions (sending a message), feedback should be modest. For infrequent/major events (failover, backend failure), feedback should be substantial — a visible alert or toast, not a silent state change.

### Step 1: Persistent Connection Indicator

**What:** A status strip in the Brutus header showing the currently active backend with a traffic-light dot.

**Current state:** The header shows `BRUTUS` title + `● idle` / `● streaming` status. This tells the user about message flow but nothing about the backend.

**Target state:**
```
BRUTUS                          ● saturn-lab (p10) · idle         [Clear]
```

When streaming:
```
BRUTUS                          ● saturn-lab (p10) · streaming    [Clear]
```

When no backends:
```
BRUTUS                          ● no backends · run discover      [Clear]
```

The colored dot follows the universal traffic-light pattern used by Traefik, Kong, Cloudflare, Consul, and HAProxy [HAProxy 2.x stats specification; Traefik v3 dashboard docs]:
- **Green** — connected, healthy
- **Yellow** — degraded (high latency or circuit breaker half-open)
- **Red** — all backends unreachable

This satisfies Nielsen's response time thresholds [Nielsen, *Usability Engineering*, 1993, ch. 5]: the dot updates within 0.1s of state change (feels instantaneous), and backend resolution happens within 1s (subtle spinner suffices during connection).

### Step 2: Per-Message Backend Attribution

**What:** A subtle metadata line below each assistant response showing which backend handled it.

**Pattern source:** This is the access-log-as-metadata pattern from HAProxy (`BackendAddr` in access logs) and Traefik (`BackendName` in structured logs) surfaced to the end user. OpenRouter implements this as a collapsible response footer showing provider, token count, latency, and cost [OpenRouter chat UI]. Open WebUI shows similar metadata for multi-backend setups [Open WebUI model selection UI].

**Implementation:** The `X-Brutus-Service` and `X-Brutus-Model` response headers already exist in the API (`web.py:501-504`). The frontend already reads them (`app.js:2007-2009`) and displays `brutus → ${service} // ${model}` in the `.meta` element. Extend this to include latency:

```
brutus → saturn-lab // llama-3.1-8b · 2.3s · 542 tok/s
```

After completion, the meta line updates with final stats. This closes Norman's Gulf of Evaluation [Norman, 2013] — the user can perceive which backend handled their request and how well it performed, without investigating.

The metadata should use muted styling (smaller font, `var(--muted)` color) per Stephen Few's principle of minimizing decoration [Few, *Information Dashboard Design*, 2006] — it shouldn't compete with the response content.

### Step 3: Failover Notification

**What:** When Brutus tries backend A and falls through to backend B, insert a system message in the chat stream.

**Pattern source:** Cloudflare and Kong Konnect use toast/banner notifications for failover events. HAProxy and Envoy use event logs with timestamped entries [Envoy admin `/clusters` endpoint docs]. Chat applications (Slack, Discord) show system events inline ("User joined the channel"). The inline approach is less intrusive than a modal and more discoverable than a status bar change.

**Implementation:** Currently, the failover loop in `web.py:443-510` silently iterates candidates. Add a mechanism to report which backends were skipped:

```
⚠ saturn-lab unavailable (circuit breaker open) → routed to saturn-home
```

This should appear as a subtle system message in the chat stream — not a modal dialog (which would violate Shneiderman's Rule 3 by treating ambient information as a workflow interruption). The styling should match system messages: smaller text, muted color, no bubble.

### Step 4: Live Backend Health Panel

**What:** Expand the existing "Backends" sidebar section from a static list to a live health display.

**Current state:** `loadBrutusBackends()` in `app.js` renders discovered services as a static list with colored dots, refreshed only when the Brutus tab is opened.

**Target state:** A panel modeled on HAProxy's stats table [HAProxy 2.x stats page specification] but simplified for a chat context:

```
Backends
  ● saturn-lab      p10   llama-3.1-8b    45ms
  ● saturn-home     p20   mistral-7b     120ms
  ○ joey-laptop     p50   —              DOWN
```

Each row shows: health dot, service name, priority, active model, latency. The panel auto-refreshes on a 20-second interval (matching Saturn's health poll cycle). Circuit breaker state is encoded in the dot color:
- **Green (●)** — closed, healthy
- **Yellow (●)** — half-open, probing
- **Red (○)** — open, requests blocked
- **Gray (○)** — not discovered

This follows the information radiator pattern [Cockburn, 2002] — glanceable, ambient, real-time. The panel uses Few's "small multiples" principle [Few, 2006] — the same visualization repeated per service.

### Step 5: Streaming State Feedback

**What:** Distinguish between connection delay and active streaming in the UI.

**Pattern source:** Nielsen's response time thresholds [Nielsen, 1993] define three perceptual ranges: <0.1s (instantaneous), <1s (noticeable but in flow), >10s (attention wanders). The period between sending a message and receiving the first token often exceeds 1s (model loading, queue wait). Without feedback, users cannot tell if the system is working or frozen — this is the Gulf of Evaluation applied to streaming [Norman, 2013].

ChatGPT's reasoning models (o1) show a "Thinking..." phase with elapsed time. llmcord uses a typing indicator during initial latency and a `⚪` suffix during streaming [jakobdylanc/llmcord, issue #75 discussion].

**Implementation:** Currently the UI shows "routing..." immediately and switches to streaming as tokens arrive. Add a three-phase indicator:

1. **"routing..."** (0–200ms) — selecting backend
2. **"connecting to saturn-lab..."** (200ms–first token) — waiting for TTFT
3. **Streaming content with blinking cursor** (first token–done)

If the connection phase exceeds 5s with no tokens, show: "Still waiting for saturn-lab... (model may be loading)". This reassures the user without false precision [Shneiderman Rule 3: informative feedback proportional to action significance].

### Step 6: QR Code and Remote Access Context

**What:** The sidebar already has QR code + tunnel management. Improve the mental model for what the QR code means.

The QR code currently points to `<tunnel-url>/#brutus`. When scanned from a phone, this deep-links directly to the Brutus chat tab. The remote user gets the same chat interface, connected through the cloudflared tunnel back to the LAN.

Add a brief contextual label above the QR:
```
Scan to chat from anywhere
Your messages route through this machine to LLM backends on your network.
```

This bridges the conceptual mapping [Norman, 2013] between "scan a QR code" and "talk to an LLM on my home network." Without it, the QR code is meaningless to someone who doesn't already understand the architecture.

### Pattern Summary

| UI Element | Pattern Source | Level | Purpose |
|---|---|---|---|
| Connection indicator | Traffic-light dots [Traefik, HAProxy, Consul] | 1 (always visible) | Ambient backend awareness |
| Per-message attribution | Access-log metadata [HAProxy, OpenRouter] | 1 (always visible) | Close Gulf of Evaluation |
| Failover notification | Inline system message [Slack, Discord events] | 2 (on event) | Inform on routing change |
| Backend health panel | Information radiator [Cockburn, 2002] | 2 (on click) | Service health at a glance |
| Streaming phases | Response time thresholds [Nielsen, 1993] | 1 (always visible) | Reassure during latency |
| QR context label | Conceptual mapping [Norman, 2013] | 1 (always visible) | Explain remote access |

### Anti-Patterns to Avoid

- **Don't show raw network details by default** — IP addresses, port numbers, mDNS records violate Norman's mapping principle. Users think in service names, not `192.168.1.42:8080` [Norman, 2013].
- **Don't use modals for status** — status is ambient information, not a workflow interruption [Shneiderman Rule 3].
- **Don't animate gratuitously** — a smooth color transition is fine; a bouncing icon is noise [Few, *Information Dashboard Design*, 2006].
- **Don't hide all status behind a menu** — the whole point of visibility of system status is that it's visible without user action [Nielsen, Heuristic #1].
- **Don't build a full monitoring dashboard** — that's Grafana's job. The chat UI shows just enough to close the evaluation gulf, with progressive disclosure for power users [Nielsen, "Progressive Disclosure," 2006].

## Discussion

### Why Discord

The key insight is that Discord solves three hard problems for free:
- **NAT traversal**: The bot opens an outbound WebSocket to Discord's gateway. No inbound ports, no public IP needed.
- **Authentication**: Discord's OAuth and DM permissions ensure only you can talk to the bot.
- **Client availability**: Discord runs on every platform — phone, laptop, browser, desktop. No custom client needed.

### Why the Web UI Tab Exists Alongside Discord

The Web UI tab provides the same remote access capability via cloudflared tunnels instead of Discord's gateway. The tradeoff: cloudflared requires installing a binary and creates a dependency on Cloudflare's Argo tunnel infrastructure, but it gives full control over the chat UI (streaming, markdown rendering, configuration) that Discord's embed system constrains. The Web UI also serves as a local-network chat interface even without remote access — users on the LAN don't need Discord or a tunnel.

### Why This Matters for Saturn

Saturn's thesis is that AI access should be a network-level utility. Brutus extends that thesis beyond the LAN boundary without compromising the zero-configuration principle. The user's mental model stays the same: "I talk, I get a response." The infrastructure is invisible.

This also makes Saturn demonstrable to anyone — an advisor, a thesis committee member, a friend. "Scan this QR code" or "DM this bot" is a far more compelling demo than "install this library and run this script on the same network."

### Tradeoffs

- **Latency**: Discord adds ~100-300ms round-trip vs direct LAN access. Cloudflared adds ~50-150ms. Acceptable for chat.
- **Message limits**: Discord: 2000 chars per message (4096 in embeds). Web UI: no limit. Long Discord responses need splitting; the Web UI handles this natively.
- **Availability**: Depends on Discord's uptime (99.9%+) or Cloudflare's tunnel infrastructure, plus the host machine being powered on and connected.
- **Privacy**: Messages transit Discord's or Cloudflare's servers. For a personal bot with personal LLM backends, this is acceptable. For sensitive enterprise use, it wouldn't be.

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

### Multi-Model Chat UI Patterns

**Sources:**
- OpenRouter chat interface — model+provider separation, routing details disclosure
- Open WebUI (formerly Ollama WebUI) — multi-backend grouping, connection status dots, tokens/sec display
- LibreChat — provider tabs, preset system, cost estimation
- LobeChat — plugin architecture, capability badges
- text-generation-webui (oobabooga) — GPU memory bars, generation speed display
- Poe by Quora — bot abstraction model
- ChatGPT — tier-based model switcher, capacity warnings

**Findings:**

*Abstraction spectrum:* Multi-model UIs range from maximum abstraction (Poe: users see "bots," not models or providers) to maximum transparency (Open WebUI: users see backends, health dots, tokens/sec, GPU utilization). Consumer products lean abstract; developer/power-user tools lean transparent. Saturn occupies the same niche as Open WebUI — infrastructure-level routing for power users who want visibility.

*Metadata display timing:* The most informative UIs show a response metadata footer after completion: `[Claude 3.5 Sonnet · via Anthropic · 1,247 tokens · 2.3s · 542 tok/s]`. OpenRouter and Open WebUI implement this pattern. During streaming, Open WebUI and text-generation-webui show live tokens/sec.

*Health communication:* Open WebUI shows connection status indicators per backend (green = connected, red = unreachable) with backend response time in settings. ChatGPT shows capacity warnings as inline banners ("This model is experiencing high demand"). OpenRouter maintains a separate provider status page.

*Auto vs. manual routing:* OpenRouter defaults to automatic provider routing but allows users to pin a specific provider. This two-layer model (auto by default, manual on demand) maps directly to how Brutus should work — auto-route by priority, but let users pin a backend if needed.

**Recommendations:**
- Default to clean, abstracted experience (Brutus auto-routes). Make routing info available on demand through progressive disclosure.
- Show per-message metadata footer with service, model, latency, and tokens/sec after completion.
- Show live tokens/sec during streaming — valuable when backends have vastly different hardware.
- Allow pinning a specific backend for a conversation (power user feature, not default).

---

### Gateway & Load Balancer Dashboard Patterns

**Sources:**
- Kong Gateway Manager / Konnect — upstream targets panel, request detail view
- Traefik v3 Dashboard — router → service → server hierarchy
- HAProxy 2.x Stats Page — tabular server status with session rates, response times
- Envoy Admin UI (`/clusters`) — health flags, outlier detection ejection
- Cloudflare Load Balancing Dashboard — pool/origin cards, health timeline
- Netflix Hystrix Dashboard (archived) — multi-dimensional circuit breaker glyph
- Resilience4j Dashboard — ring buffer visualization
- Istio/Kiali — service graph with circuit breaker badges

**Findings:**

*Routing visibility:* None of these dashboards show per-request routing in real-time. Routing decisions are metadata on request records (Kong Vitals, Traefik access logs with `BackendAddr`, Envoy `%UPSTREAM_HOST%` format strings). The dashboard shows aggregate state. Saturn's per-message attribution is more granular than what gateways typically provide.

*Circuit breaker visualization:* The Hystrix pattern encodes multiple dimensions into a single glyph — circle size = request volume, color = error rate, fill = circuit state. For simpler UIs, the three-dot traffic light (green/yellow/red) with tooltip is standard. Envoy shows outlier detection as binary ejected/not-ejected with timestamps. Resilience4j shows a ring buffer of recent call results as a donut chart.

*Failover communication:* Cloudflare and Kong use toast/banner notifications. HAProxy and Envoy use scrolling event logs with timestamps. The inline system message pattern (inserting a status event into the conversation stream) is unique to chat UIs and more natural for Brutus than either approach.

*Health at a glance:* HAProxy's dense tabular layout with color-coded status cells is the gold standard for operators. For end users, Cloudflare's card-based pool layout with health timeline strips is more approachable. Saturn's sidebar panel should be closer to Cloudflare's card model than HAProxy's table.

**Recommendations:**
- Per-message attribution exceeds what most gateways provide — lean into this as a differentiator.
- Use the three-color dot system for circuit breaker state (skip the Hystrix multi-dimensional encoding — too complex for a chat UI).
- Insert failover events as inline system messages, not toasts or separate logs.
- Model the sidebar health panel on Cloudflare's card layout, not HAProxy's dense table.

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
- Nielsen, "10 Usability Heuristics for User Interface Design" (1994); *Usability Engineering* (1993)
- Nielsen & Molich, "Heuristic evaluation of user interfaces," *Proc. ACM CHI'90* (1990)
- Nielsen, "Progressive Disclosure," NNGroup (2006)
- Shneiderman, *Designing the User Interface*, 6th ed. (2016)
- Norman, *The Design of Everyday Things*, revised ed. (2013)
- Cockburn, *Agile Software Development* (2002) — Information Radiator
- Few, *Information Dashboard Design* (2006) — Dashboard anti-patterns, small multiples
- Cooper et al., *About Face*, 4th ed. (2014) — "Informing and Providing Feedback" (ch. 18)
- Tidwell, *Designing Interfaces*, 3rd ed. (2020) — Progress indicator taxonomy (ch. 9)
- Wickens & Hollands, *Engineering Psychology and Human Performance*, 4th ed. (2012)

**Findings:**

*Proxy taxonomy:* Brutus is an **application gateway with protocol translation** (RFC 7230 §5.7). It composes two GoF patterns: **Adapter** (translates Discord WS events / browser HTTP ↔ OpenAI HTTP — different interfaces) and **Proxy** (surrogate for LLM backends with added service discovery, auth, and history). Fowler's Gateway pattern refines this: a Gateway wraps a "foreign" API with a convenient local API. Brutus defines a "DM me and I reply" / "type and get a response" interface that wraps the OpenAI API.

*NAT traversal:* Discord's gateway is functionally a **TURN relay** (RFC 5766) with persistent WebSocket connections. Cloudflared tunnels use the same outbound-persistent-connection principle. The tradeoff is sovereignty — you depend on Discord's/Cloudflare's uptime and ToS.

*Service discovery taxonomy:* Three categories exist — zero-config/mDNS (Bonjour, Avahi, Saturn), CP-consistent (Consul, etcd, ZooKeeper), AP-available (Eureka, Nacos). Saturn occupies zero-config: client-side discovery, no central registry, no single point of failure, no consistency protocol.

*Status communication lineage:* The problem of communicating proxy behavior to users is a specific instance of Nielsen's Heuristic #1 (1994), which itself descends from Shneiderman's Rule 3 (1987) and Norman's action cycle model (1988). The solution space is well-established: persistent status indicators, progressive disclosure, and proportional feedback. The novel aspect is applying these patterns to an LLM chat gateway rather than a traditional web application.

**Recommendations:**
- Frame Brutus in the thesis as an "application gateway with protocol translation using a hosted TURN-equivalent relay" — places it in 30+ years of established taxonomy.
- Describe failover as "Lazy Pirate with ordered failover" (Hintjens terminology). Circuit breakers are the natural extension (Paranoid Pirate's heartbeating = Saturn's health polling).
- Frame the UI communication design as applying Nielsen/Shneiderman/Norman to a novel domain (LLM chat gateways). The principles are established; the application is new.

---

### Implementation Pattern Summary

| Component | Pattern | Source | Implementation |
|---|---|---|---|
| Bot architecture | Application Gateway + Adapter | RFC 7230, GoF (1994) | Protocol translation: Discord WS / HTTP ↔ OpenAI HTTP |
| Reference impl | llmcord fork | jakobdylanc/llmcord | Extract message-chain + streaming-embed patterns |
| Service discovery | Client-side mDNS, priority sort | RFC 6762/6763 | Saturn's `SaturnDiscovery` class |
| Message flow | Request-Reply + Content Enricher + Message Translator | Hohpe & Woolf (2003) | Enrich with history, translate protocols |
| Failover | Lazy Pirate with ordered failover | Hintjens (2013) | For-loop over priority-sorted backends |
| Resilience | Circuit Breaker + layered Timeouts | Nygard (2018) | Per-backend breaker, 5s/30s/15s/120s timeouts |
| Backoff | Full Jitter exponential backoff | AWS/Brooker (2015) | `random.uniform(0, min(cap, base * 2^n))` |
| Conversation state | Bounded deque + optional token budget | Classical LRU / sliding window | `deque(maxlen=50)` per user |
| Streaming UX | Embed edits at 1s interval | llmcord (proven) | Color-coded embeds, smart splitting |
| Dependencies | Minimal (4 packages) | llmcord pattern | `discord.py`, `openai`, `httpx`, `pyyaml` |
| Status communication | Visibility of System Status | Nielsen (1994), Norman (2013) | Persistent indicator, per-message attribution |
| Progressive disclosure | Three-level status hierarchy | Nielsen (2006), Shneiderman (1987) | Dot → panel → diagnostic view |
| Health display | Information radiator | Cockburn (2002), Few (2006) | Sidebar with traffic-light dots per backend |
| Failover UX | Inline system messages | Chat UI convention, Cloudflare/Kong | System message in chat stream on backend switch |
