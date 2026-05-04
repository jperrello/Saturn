# README_PATTERNS.md
> Distilled patterns for Saturn's README rewrite. Writer: read this first.

## The 5-second test

A visitor decides in 5 seconds, without scrolling, whether Saturn is worth their attention. Concrete bullets observed across the sample:

- **Tagline first, before anything else.** One sentence, what it IS + who it's FOR. FastAPI: "FastAPI framework, high performance, easy to learn." python-zeroconf: "Multicast DNS Service Discovery for Python." Tailscale: "Private WireGuard networks made easy."
- **Badges earn their slot or get cut.** CI status + version are universal. Coverage badges only matter if the number is actually high. Ollama ships with zero badges and loses nothing. python-zeroconf's 5 badges (CI, PyPI, Codecov, Codspeed, RTD) is the upper limit before noise.
- **One runnable codeblock above the fold, OR a screenshot.** Never both, never neither.
- **Install one-liner.** `curl | sh` for daemons (Ollama). `pip install` only when the project IS Python (FastAPI, zeroconf). `go install` for Go-native tools (Tailscale).

## Tagline patterns

Verbatim from sample:

1. **"FastAPI framework, high performance, easy to learn, fast to code, ready for production"** — works because it stacks 4 concrete promises after the noun.
2. **"Start building with open models."** (Ollama) — works because verb-first; tells you what YOU do.
3. **"Private WireGuard® networks made easy"** (Tailscale) — works because it names the protocol it builds on + the value-add.
4. **"Multicast DNS Service Discovery for Python"** (python-zeroconf) — works because it's literally what + for whom in 6 words.
5. **"Consul is a distributed, highly available, and data center aware solution to connect and configure applications across dynamic, distributed infrastructure."** — weak because 22 words, 4 adjectives before the verb. Saturn must not write like this.
6. **"A simple, secure and performant communications system for digital systems, services and devices."** (NATS) — weak because three abstract adjectives + four abstract nouns; reader still doesn't know what NATS DOES.
7. **"Every site on HTTPS"** (Caddy) — works because it's a *promise*, not a description. Four words. Saturn should consider a promise-shaped tagline.
8. **"A continuous file synchronization program"** (Syncthing) — works because it names the verb (synchronize) and the thing (files); weak because no audience hint.

## Canonical section order

Order recurring in winning READMEs:

1. Tagline + badges
2. What is X (2-3 lines max)
3. Quickstart (runnable codeblock, ≤ 30s to result)
4. Why X / when to use
5. Features (bulleted, terse)
6. Install (multiple platforms)
7. Examples (link to docs/examples/)
8. Docs link
9. Community / Contributing
10. License

Ollama deviates by putting **Download** before everything — works because the product IS the binary. Saturn should NOT copy this; Saturn is a protocol, not a binary. Caddy puts **Features** then **Install** before **Quick start** — survives because Caddy users already know they want a web server. Saturn cannot assume that level of pre-conviction; lead with quickstart, justify after.

Consul leads with feature-list headings (Multi-Datacenter, Service Mesh, API Gateway, Service Discovery, Health Checking) BEFORE Quick Start. This is a HashiCorp pattern; it works for enterprise sales but is hostile to a 5-second visitor. Saturn should invert this.

## Code-block patterns

- **Hero codeblock must be runnable in 30s.** Ollama: `curl -fsSL https://ollama.com/install.sh | sh`. FastAPI: an actual `from fastapi import FastAPI` 8-liner you can paste.
- **Multi-language tabs (curl + Go + Python)** appear where the project is a *protocol/API* with multiple clients. Saturn is one of these — lead with `dns-sd` (zero install on macOS) + `curl`, then Go example.
- **Show output, not just input.** python-zeroconf's `update_service` example shows the print line. Without output, the reader has to imagine what success looks like.

## Anti-patterns

- Auto-generated TOC at top — wastes the 5 seconds.
- Wall-of-text intro before any code (python-zeroconf flirts with this — "Compatible with… Compared to… Python compatibility" before any usage).
- "Why I built this" before "What this does."
- Python install for non-Python projects.
- Missing screenshots for visual products.
- Stale badges — CI badge red for months destroys trust faster than no badge.
- Logo eats a full screen above the fold.
- Section headers like "Sponsors" or "Opinions" before "Example" (FastAPI's actual order — only survives because the project is famous; Saturn cannot afford this).
- **No hero codeblock at all.** Consul, NATS, and Syncthing all skip a runnable hero block. Result: visitor cannot tell in 5 seconds what using it looks like. Saturn must not repeat this.
- **Adjective-stacked taglines** (Consul, NATS) — "distributed, highly available, data center aware" is noise. Pick one promise.

## The Saturn-shaped README

Saturn is a **protocol**, not a Python package. The README must establish that in 5 seconds and lead with `curl` / Go.

**Tagline candidates (3 to choose from):**

1. "Saturn — mDNS-discoverable AI endpoints. curl-friendly, zero-config on your LAN."
2. "Saturn — DNS-SD for AI. Discover and call any model on your network with one query."
3. "Saturn — the zero-config discovery layer for local AI. Speak mDNS, get an OpenAI-shaped endpoint."

**Section list (final, ordered):**

1. Tagline + 2 badges (spec version, conformance test status)
2. What is Saturn (2 lines: "Saturn is a protocol — mDNS/DNS-SD service type `_saturn._tcp` — that lets any AI endpoint announce itself on a LAN. Clients discover and call it with stock tools.")
3. Quickstart (the hero block below)
4. Why Saturn (3 bullets: zero-config, transport-agnostic, OpenAI-compatible by default)
5. Implementations (table: Go server, Python server, JS client, etc., linking out)
6. TXT record fields (the 4-5 you actually need to know — full schema lives in `docs/spec.md`)
7. Conformance & test suite (link)
8. Spec (link to `docs/spec.md`)
9. Contributing
10. License

**Hero codeblock (the actual block):**

```bash
# 1. Discover Saturn endpoints on your LAN (macOS/Linux, no install)
$ dns-sd -B _saturn._tcp .local
Browsing for _saturn._tcp.local
  Add  3 llama-3-8b._saturn._tcp.local.
  Add  3 whisper-v3._saturn._tcp.local.

# 2. Resolve and call one — same shape as OpenAI
$ curl http://llama-3-8b.local:8080/v1/chat/completions \
    -H 'content-type: application/json' \
    -d '{"model":"default","messages":[{"role":"user","content":"hi"}]}'
{"id":"...","choices":[{"message":{"content":"Hello!"}}]}
```

**What does NOT belong in README** (push to `docs/`):

- Full protocol spec
- Complete TXT-record schema (only the 4-5 most-used fields belong inline)
- Security / threat model
- Every config field of the reference server
- Deployment guides (k8s, systemd, etc.)
- Comparison matrix vs. every other discovery protocol

## Sources cross-read

- [tiangolo/fastapi](https://github.com/tiangolo/fastapi) — gold standard for tagline + hero block
- [ollama/ollama](https://github.com/ollama/ollama) — modern protocol-shaped, zero badges
- [tailscale/tailscale](https://github.com/tailscale/tailscale) — network protocol positioning
- [python-zeroconf/python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) — mDNS-direct reference
- [hashicorp/consul](https://github.com/hashicorp/consul) — service-discovery anti-pattern (feature headings before quickstart)
- [nats-io/nats-server](https://github.com/nats-io/nats-server) — adjective-stacked tagline cautionary tale
- [caddyserver/caddy](https://github.com/caddyserver/caddy) — promise-shaped tagline ("Every site on HTTPS")
- [syncthing/syncthing](https://github.com/syncthing/syncthing) — verb-first minimal tagline; missing hero block
