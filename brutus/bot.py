import os
import asyncio
import logging
import random
from collections import deque
from dataclasses import dataclass, field

import discord
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("brutus")

# --- config ---

EDIT_DELAY = 1.0
EMBED_LIMIT = 4096
SPLIT_LIMIT = EMBED_LIMIT - 10
MAX_HISTORY = 50
MAX_USERS = 100
HEALTH_INTERVAL = 20
CONNECT_TIMEOUT = 5.0
FIRST_BYTE_TIMEOUT = 30.0
INTER_CHUNK_TIMEOUT = 15.0
TOTAL_TIMEOUT = 180.0
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN = 30.0


# --- circuit breaker ---

@dataclass
class Breaker:
    failures: int = 0
    opened_at: float = 0.0

    @property
    def is_open(self):
        if self.failures < BREAKER_THRESHOLD:
            return False
        import time
        if time.time() - self.opened_at > BREAKER_COOLDOWN:
            self.failures = 0
            return False
        return True

    def record_failure(self):
        import time
        self.failures += 1
        if self.failures >= BREAKER_THRESHOLD:
            self.opened_at = time.time()

    def record_success(self):
        self.failures = 0


# --- conversation state ---

@dataclass
class Conversation:
    messages: deque = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))


# --- bot state ---

breakers: dict[str, Breaker] = {}  # keyed by service name
conversations: dict[int, Conversation] = {}  # keyed by user id
user_models: dict[int, str] = {}  # per-user model selection
service_health: dict[str, bool] = {}  # keyed by endpoint
seen_messages: set[int] = set()  # dedup on reconnect
discovery = None
_health_task = None


def get_breaker(name):
    if name not in breakers:
        breakers[name] = Breaker()
    return breakers[name]


def get_conversation(uid):
    if uid not in conversations:
        if len(conversations) > MAX_USERS:
            oldest = next(iter(conversations))
            del conversations[oldest]
        conversations[uid] = Conversation()
    return conversations[uid]


def dedup(mid):
    if mid in seen_messages:
        return True
    seen_messages.add(mid)
    if len(seen_messages) > 1000:
        to_remove = list(seen_messages)[:500]
        for m in to_remove:
            seen_messages.discard(m)
    return False


# --- streaming ---

COLOR_PENDING = 0xFFA500
COLOR_DONE = 0x2D7D46


async def stream_response(channel, messages, model, reply_to):
    global discovery
    if discovery is None:
        log.error("stream_response called but discovery is None — on_ready may not have fired")
        embed = discord.Embed(description="Bot not fully initialized.", color=0xFF0000)
        await channel.send(embed=embed, reference=reply_to)
        return None

    services = discovery.get_all_services()
    if not services:
        log.warning("stream_response: discovery returned zero services")
        embed = discord.Embed(description="No Saturn backends available.", color=0xFF0000)
        await channel.send(embed=embed, reference=reply_to)
        return None

    log.info(f"stream_response: {len(services)} services discovered: {[s.name for s in services]}")

    healthy = [s for s in services if not get_breaker(s.name).is_open
               and service_health.get(s.effective_endpoint, True)]

    if not healthy:
        log.warning("stream_response: no healthy services, falling back to non-tripped breakers")
        healthy = [s for s in services if not get_breaker(s.name).is_open]

    if not healthy:
        tripped = [s.name for s in services if get_breaker(s.name).is_open]
        log.error(f"stream_response: all backends down — tripped breakers: {tripped}, "
                  f"health status: {service_health}")
        embed = discord.Embed(description="All backends are down.", color=0xFF0000)
        await channel.send(embed=embed, reference=reply_to)
        return None

    log.info(f"stream_response: trying {len(healthy)} healthy backends: "
             f"{[(s.name, s.effective_endpoint) for s in healthy]}, model={model!r}")

    for service in healthy:
        key = service.ephemeral_key or "sk-no-key-required"
        log.info(f"stream_response: attempting {service.name} at {service.effective_endpoint} "
                 f"(key={'ephemeral' if service.ephemeral_key else 'none'})")
        client = AsyncOpenAI(
            base_url=service.effective_endpoint,
            api_key=key,
            timeout=httpx.Timeout(TOTAL_TIMEOUT, connect=CONNECT_TIMEOUT),
        )
        try:
            return await _stream_from(client, channel, messages, model, reply_to, service)
        except Exception as e:
            log.warning(f"Backend {service.name} failed: {type(e).__name__}: {e}", exc_info=True)
            get_breaker(service.name).record_failure()
            continue

    log.error("stream_response: exhausted all backends without success")
    embed = discord.Embed(description="All backends failed to respond.", color=0xFF0000)
    await channel.send(embed=embed, reference=reply_to)
    return None


async def _stream_from(client, channel, messages, model, reply_to, service):
    effective_model = model or (service.models[0] if service.models else None)
    if not effective_model:
        try:
            resp = await client.models.list()
            if resp.data:
                effective_model = resp.data[0].id
                log.info(f"_stream_from: fetched model {effective_model!r} from {service.name}")
        except Exception as e:
            log.warning(f"_stream_from: failed to fetch models from {service.name}: {e}")
    if not effective_model:
        raise ValueError(f"No model available for {service.name}")
    kwargs = {"model": effective_model, "messages": messages, "stream": True}
    log.info(f"_stream_from: starting stream to {service.name} "
             f"model={effective_model!r} msg_count={len(messages)}")

    collected = ""
    bot_msg = None
    last_edit = 0
    chunk_count = 0

    try:
        async with channel.typing():
            try:
                stream = await asyncio.wait_for(
                    client.chat.completions.create(**kwargs),
                    timeout=FIRST_BYTE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.error(f"_stream_from: first-byte timeout ({FIRST_BYTE_TIMEOUT}s) "
                          f"from {service.name} at {service.effective_endpoint}")
                raise
            except Exception as e:
                log.error(f"_stream_from: create() failed for {service.name}: "
                          f"{type(e).__name__}: {e}", exc_info=True)
                raise

            async for chunk in stream:
                chunk_count += 1
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta or not delta.content:
                    continue
                collected += delta.content

                now = asyncio.get_event_loop().time()
                if now - last_edit >= EDIT_DELAY:
                    display = collected[:SPLIT_LIMIT] + " ⚪" if len(collected) > 0 else collected
                    embed = discord.Embed(description=display, color=COLOR_PENDING)
                    try:
                        if bot_msg is None:
                            bot_msg = await channel.send(embed=embed, reference=reply_to)
                        else:
                            await bot_msg.edit(embed=embed)
                    except discord.HTTPException as e:
                        log.warning(f"_stream_from: discord edit/send failed mid-stream: "
                                    f"{e.status} {e.text}")
                    last_edit = now
    except discord.HTTPException as e:
        log.error(f"_stream_from: discord typing/send error: {e.status} {e.text}")
        raise
    except Exception as e:
        log.error(f"_stream_from: stream loop failed after {chunk_count} chunks, "
                  f"{len(collected)} chars collected: {type(e).__name__}: {e}")
        raise

    log.info(f"_stream_from: stream complete from {service.name} — "
             f"{chunk_count} chunks, {len(collected)} chars")

    if not collected:
        log.warning(f"_stream_from: empty response from {service.name} after {chunk_count} chunks")
        collected = "*Empty response.*"

    chunks = split_message(collected)
    try:
        if bot_msg is None:
            embed = discord.Embed(description=chunks[0], color=COLOR_DONE)
            bot_msg = await channel.send(embed=embed, reference=reply_to)
        else:
            embed = discord.Embed(description=chunks[0], color=COLOR_DONE)
            await bot_msg.edit(embed=embed)

        for extra in chunks[1:]:
            embed = discord.Embed(description=extra, color=COLOR_DONE)
            bot_msg = await channel.send(embed=embed, reference=bot_msg)
    except discord.HTTPException as e:
        log.error(f"_stream_from: failed to send final embed: {e.status} {e.text}")
        raise

    get_breaker(service.name).record_success()
    return collected


def split_message(text):
    if len(text) <= SPLIT_LIMIT:
        return [text]

    parts = []
    in_fence = False
    while len(text) > SPLIT_LIMIT:
        cut = text[:SPLIT_LIMIT]
        # find natural break point
        for sep in ["\n\n", "\n", " "]:
            idx = cut.rfind(sep)
            if idx > SPLIT_LIMIT // 2:
                cut = text[:idx + len(sep)]
                break

        # track code fences
        fence_count = cut.count("```")
        if (in_fence and fence_count % 2 == 0) or (not in_fence and fence_count % 2 == 1):
            cut = cut.rstrip() + "\n```"
            in_fence = not in_fence
        elif in_fence:
            pass

        parts.append(cut)
        text = text[len(cut):]
        if in_fence:
            text = "```\n" + text
            in_fence = True

    if text:
        parts.append(text)
    return parts


# --- health checker ---

async def health_loop():
    global discovery
    log.info("health_loop: starting background health checker "
             f"(interval={HEALTH_INTERVAL}s)")
    async with httpx.AsyncClient(timeout=5.0) as http:
        while True:
            try:
                if discovery is None:
                    log.warning("health_loop: discovery is None, skipping cycle")
                    await asyncio.sleep(HEALTH_INTERVAL)
                    continue
                services = discovery.get_all_services()
                for s in services:
                    endpoint = s.effective_endpoint
                    url = endpoint.rstrip("/").rsplit("/v1", 1)[0] + "/v1/health"
                    try:
                        resp = await http.get(url)
                        was = service_health.get(endpoint)
                        now_healthy = resp.status_code == 200
                        service_health[endpoint] = now_healthy
                        if was is not None and was != now_healthy:
                            log.info(f"health_loop: {s.name} ({endpoint}) "
                                     f"{'recovered' if now_healthy else 'went unhealthy'} "
                                     f"(status={resp.status_code})")
                        if not now_healthy:
                            log.warning(f"health_loop: {s.name} ({url}) "
                                        f"returned status {resp.status_code}")
                    except httpx.ConnectError as e:
                        service_health[endpoint] = False
                        log.warning(f"health_loop: {s.name} ({url}) connect failed: {e}")
                    except httpx.TimeoutException as e:
                        service_health[endpoint] = False
                        log.warning(f"health_loop: {s.name} ({url}) timed out: {e}")
                    except Exception as e:
                        service_health[endpoint] = False
                        log.warning(f"health_loop: {s.name} ({url}) error: "
                                    f"{type(e).__name__}: {e}")
            except Exception as e:
                log.error(f"health_loop: outer loop error: {type(e).__name__}: {e}",
                          exc_info=True)
            await asyncio.sleep(HEALTH_INTERVAL)


# --- discord bot ---

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    log.info(f"Brutus online as {bot.user} (id={bot.user.id})")
    global discovery, _health_task
    if discovery is not None:
        log.info("on_ready: reconnect detected, reusing existing discovery")
        return
    try:
        from saturn.discovery import SaturnDiscovery
        discovery = SaturnDiscovery()
        log.info("on_ready: SaturnDiscovery initialized")
    except Exception as e:
        log.error(f"on_ready: failed to initialize SaturnDiscovery: "
                  f"{type(e).__name__}: {e}", exc_info=True)
        return
    _health_task = bot.loop.create_task(health_loop())


@bot.event
async def on_message(msg):
    if msg.author == bot.user or msg.author.bot:
        return

    is_dm = isinstance(msg.channel, discord.DMChannel)
    mentioned = bot.user in msg.mentions

    if not is_dm and not mentioned:
        return

    if dedup(msg.id):
        log.debug(f"on_message: dedup hit for msg {msg.id}")
        return

    log.info(f"on_message: from {msg.author} (id={msg.author.id}) "
             f"in {'DM' if is_dm else f'#{msg.channel}'} — "
             f"{len(msg.content)} chars")

    text = msg.content.strip()
    if mentioned:
        text = text.replace(f"<@{bot.user.id}>", "").strip()
    if not text:
        log.debug("on_message: empty after stripping mention, ignoring")
        return

    # commands
    if text.lower() == "/help":
        help_text = (
            "**Brutus** — Saturn LLM gateway over Discord.\n\n"
            "DM me any message and I'll forward it to the best available Saturn backend "
            "on the local network. Responses stream back as embeds — orange while generating, "
            "green when complete.\n\n"
            "I remember context across messages (up to 50 turns) so you can have multi-turn conversations.\n\n"
            "**Commands:**\n"
            "• `/help` — show this message\n"
            "• `/clear` — reset your conversation history\n"
            "• `/status` — list discovered Saturn services with health indicators\n"
            "• `/model <name>` — pin to a specific model (e.g. `/model gpt-4`)\n"
            "• `/model clear` — reset to default model\n\n"
            "**How it works:**\n"
            "• Discovers backends via mDNS (`_saturn._tcp.local.`)\n"
            "• Tries backends in priority order with circuit breakers\n"
            "• Background health checks every 20s\n"
            "• Layered timeouts: 5s connect, 30s first byte, 180s total"
        )
        embed = discord.Embed(title="Brutus Help", description=help_text, color=COLOR_DONE)
        await msg.channel.send(embed=embed)
        return

    if text.lower() == "/clear":
        uid = msg.author.id
        if uid in conversations:
            del conversations[uid]
        await msg.channel.send("Conversation cleared.")
        return

    if text.lower() == "/status":
        log.info(f"on_message: /status command from {msg.author}")
        services = discovery.get_all_services() if discovery else []
        if not services:
            await msg.channel.send("No Saturn services discovered.")
            return
        lines = []
        for s in services:
            healthy = service_health.get(s.effective_endpoint, None)
            icon = "🟢" if healthy else ("🔴" if healthy is False else "⚪")
            breaker = get_breaker(s.name)
            cb = " [OPEN]" if breaker.is_open else ""
            models = ", ".join(s.models) if s.models else "unknown"
            lines.append(f"{icon} **{s.name}** (pri={s.priority}) — {models}{cb}")
        embed = discord.Embed(title="Saturn Services", description="\n".join(lines), color=COLOR_DONE)
        await msg.channel.send(embed=embed)
        return

    if text.lower().startswith("/model"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            current = user_models.get(msg.author.id, "default")
            await msg.channel.send(f"Current model: `{current}`\nUsage: `/model <name>` or `/model clear`")
            return
        name = parts[1].strip()
        if name.lower() == "clear":
            user_models.pop(msg.author.id, None)
            await msg.channel.send("Model selection cleared (using default).")
        else:
            user_models[msg.author.id] = name
            await msg.channel.send(f"Model set to `{name}`.")
        return

    # regular message — send to LLM
    conv = get_conversation(msg.author.id)
    conv.messages.append({"role": "user", "content": text})

    model = user_models.get(msg.author.id)
    history = list(conv.messages)
    log.info(f"on_message: routing to LLM — model={model!r}, "
             f"history_len={len(history)}, text_preview={text[:80]!r}")

    try:
        reply = await stream_response(msg.channel, history, model, msg)
        if reply:
            conv.messages.append({"role": "assistant", "content": reply})
            log.info(f"on_message: reply stored — {len(reply)} chars")
        else:
            log.warning("on_message: stream_response returned None (no reply stored)")
    except Exception as e:
        log.error(f"on_message: stream error for user {msg.author.id}: "
                  f"{type(e).__name__}: {e}", exc_info=True)
        embed = discord.Embed(
            description=f"*Response interrupted.*\n`{type(e).__name__}: {e}`",
            color=0xFF0000,
        )
        try:
            await msg.channel.send(embed=embed, reference=msg)
        except discord.HTTPException as send_err:
            log.error(f"on_message: failed to send error embed: "
                      f"{send_err.status} {send_err.text}")


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        log.error("DISCORD_TOKEN not set in environment")
        raise SystemExit(1)
    log.info("main: starting bot")
    bot.run(token)


if __name__ == "__main__":
    main()
