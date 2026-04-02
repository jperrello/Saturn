# Troubleshooting

## No services found

`saturn discover` returns nothing.

**Causes:**

- No administrator has set up Saturn on this network.
- Firewall blocking mDNS (port 5353/UDP).
- Not on the same LAN or subnet as the Saturn service.

**Fix:** Check with your network administrator. Make sure you are on the same WiFi or wired LAN as the Saturn host.

---

## Discovery timeout

Services appear intermittently or take too long to resolve.

**Causes:**

- Congested network. Try increasing the timeout: `saturn discover --timeout 10`.
- mDNS uses multicast address `224.0.0.251`. Some routers or switches block multicast traffic.

---

## Models not loading

Service is found but no models are listed.

**Causes:**

- The upstream API (OpenRouter, DeepInfra, Ollama) is down.
- The API key has expired. This is an admin issue — contact whoever runs the service.
- The service just started. Wait a few seconds and retry.

---

## Chat not responding

Message sent but no response comes back.

**Causes:**

- Rate limit exceeded. Check your status with `GET /api/rate-limit/status`.
- The model is overloaded or unresponsive.
- Network connectivity issue between you and the service.

**Fix:** Try a different service if one is available.

---

## Web UI won't load

`saturn web` starts but the browser shows a blank page or connection refused.

**Causes:**

- Port conflict. The default port may already be in use. Try `saturn web --port 8080`.
- Firewall blocking port 3000 (the default).

---

## Context window full

Auto-compact kicked in or messages are being truncated.

**Fix:** Start a new chat session, or send shorter messages. The context window is determined by the model — there is nothing to configure on the Saturn side.

---

## Tunnel not connecting

Remote access via Cloudflare tunnel fails.

**Causes:**

- `cloudflared` is not installed or not on `PATH`.
- DNS propagation delay. Tunnels can take up to 30 seconds to become reachable after creation.
