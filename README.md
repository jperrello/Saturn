# Saturn

**Discover and call any model on your network with one query.**

Saturn is a protocol — mDNS/DNS-SD service type `_saturn._tcp.local.` — that lets any OpenAI-compatible AI endpoint announce itself on a LAN. Clients discover and call it with stock tools.

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

> **AI agents and LLMs:** read [AGENTS.md](AGENTS.md). **ML systems researchers:** read [docs/how-to/for-researchers.md](docs/how-to/for-researchers.md).

This repository is the artifact of a master's thesis at UC Santa Cruz (Joey Perrello, advised by Adam Smith). Thesis: [*Saturn: Zero-Configuration AI Service Discovery*](https://escholarship.org/uc/item/74r4d4c5#main) (eScholarship, 2026).

---

## Why Saturn

- **Zero-config.** No accounts, no per-app keys, no manual endpoint URLs. The same mechanism your laptop already uses to find printers.
- **Transport-agnostic.** Anything that can browse mDNS and speak HTTP is a conformant client — `dns-sd`, `avahi-browse`, Go, Python, Rust, TS, Lua.
- **OpenAI-compatible by default.** Discovered endpoints expose `/v1/health`, `/v1/models`, `/v1/chat/completions`. Drop the URL into any tool that takes a `base_url`.

---

## Same idea, other languages

**Go**

```bash
$ cd saturnd && go build -o saturnd ./cmd/saturnd
$ ./saturnd                                # browse + serve on :7827
$ curl http://localhost:7827/v1/agents     # discovered Saturn instances
```

**Python**

```bash
$ pip install saturn-ai
$ saturn discover                          # print every advertised service
$ curl $(saturn endpoint)/v1/models        # call the highest-priority one
```

**TypeScript**

```ts
import { createSaturn } from "ai-sdk-provider-saturn";
const saturn = createSaturn();
const services = await saturn.discover({ timeout: 2000 });
console.log(services[0].endpoint);
```

Full per-language details: [docs/integrations/](docs/integrations/index.md).

---

## Implementations

Seven reference clients across five languages and four mDNS libraries, sharing no Saturn-specific code. Interoperability comes from the wire format alone (Saturn.md:976).

| Implementation | Language | mDNS library | What it does |
|---|---|---|---|
| [`saturnd/`](saturnd/README.md) | Go | `grandcat/zeroconf` | Standalone discovery daemon; A2A/MCP surface |
| [`saturn/`](saturn/README.md) | Python | `python-zeroconf` | Reference package: discovery, server, beacon, CLI, Web UI |
| [`saturn-router/`](saturn-router/openwrt/README.md) | Rust | `mdns-sd` | Router-edge build (~2 MB, runs on a $20 OpenWRT MIPS box) |
| [`ai-sdk-provider-saturn/`](ai-sdk-provider-saturn/README.md) | TypeScript | `multicast-dns` | Vercel AI SDK provider with circuit breaking + failover |
| [`vlc_extension/`](vlc_extension/README.md) | Lua + Python | `dns-sd` CLI | Bridges Saturn into a non-AI-native host application |
| [`saturn-mcp/`](saturn-mcp/README.md) | TypeScript | `multicast-dns` | Discovery surfaced as MCP tools |
| [Open WebUI plugin](owui_saturn.py) | Python | `python-zeroconf` | Single-file backend swap for Open WebUI |

A post-thesis [OpenCode fork](https://github.com/jperrello/opencode-saturn) (TypeScript, `multicast-dns`) demonstrates agentic workflow with tool calls and streaming; it lives outside the monorepo and is not part of the canonical seven.

---

## TXT record (the wire artifact)

Saturn carries everything a client needs in one DNS-SD TXT record:

```
version=1                                 # protocol version — required
api_type=openai                           # api shape — required
deployment=cloud                          # local | cloud | network — required
priority=10                               # lower preferred — required
api_base=https://openrouter.ai/api/v1     # cloud only
ephemeral_key=eyJhbGc...                  # short-lived JWT, cloud only
rotation_interval=300                     # seconds; default 300
features=chat,tools,vision                # capability hints
```

[RFC 6763 §6.1](https://datatracker.ietf.org/doc/html/rfc6763#section-6.1) caps each TXT string at 255 bytes — JWTs fit, X.509 certs don't. That constraint shapes the credential design.

Full schema, RFC-style stability levels, and per-key prose: [docs/reference/protocol/txt-keys.md](docs/reference/protocol/txt-keys.md).

---

## Beacons and ephemeral keys

A Saturn **beacon** dispenses credentials for a cloud upstream and never proxies inference traffic:

1. Mint a scoped sub-key against the upstream with a short expiration.
2. Embed it in the `ephemeral_key` TXT field.
3. Rotate before expiry; clients re-read TXT.
4. Clients call the upstream directly — the beacon never sees prompt or completion bytes.

The reference Python beacon defaults to a 10-minute key with a 5-minute rotation interval (Saturn.md:614–615). These are reference-implementation defaults, not protocol invariants. The design bounds the dominant secret-leakage failure mode — [Meli et al.](https://www.ndss-symposium.org/wp-content/uploads/2019/02/ndss2019_04B-3_Meli_paper.pdf) found 81% of GitHub-leaked secrets are never revoked; a short-lived sub-key is dead before any scanner reaches it.

> **Security posture.** Beacon mode is for trusted local networks — the kind you'd plug a printer into. The sub-key's per-key spending cap is the actual security boundary; set `beacon.max_budget_usd` low if your threat model includes any device on the LAN. If that doesn't fit, use **proxy mode** — Saturn keeps the parent key server-side and proxies through its own authenticated `/v1/*` endpoints, gated by `SATURN_RUNNER_TOKEN` (CONFIG_FIELDS §A.2).

Full threat model, TLS posture, and `X-Forwarded-For` / `SATURN_TRUSTED_PROXIES` setup: [docs/reference/protocol/security.md](docs/reference/protocol/security.md).

---

## Roles

Saturn names three roles and concentrates configuration in exactly one of them.

- **Administrator** — deploys services, sets priorities, manages credentials. The only role that touches configuration.
- **Application developer** — calls `discover()`; receives services with URLs and credentials populated. No auth logic, no billing integration.
- **End user** — connects to the network. Nothing else.

The cognitive walkthrough in the thesis shows the application-developer step count drops 19 → 4 (−79%) and the end-user count drops 7 → 0 (−100%). Asymptotic form: `12 + 19N + 7M` (traditional) → `14 + 4N + 0M` (Saturn) over `N` developers and `M` end users. Methodology and threats to validity: [docs/how-to/for-researchers.md](docs/how-to/for-researchers.md).

---

## Conformance

A Saturn implementation in any language is five steps:

1. Browse `_saturn._tcp.local.` with any DNS-SD library.
2. Resolve SRV + TXT for each instance.
3. Validate `version=1` and parse the [TXT keys](docs/reference/protocol/txt-keys.md).
4. Sort by `priority`; pick the lowest healthy (probe `GET /v1/health`).
5. Call the [`/v1/*` HTTP API](docs/reference/protocol/http-api.md) at `api_base` (cloud) or the SRV `host:port` (local / network).

That is the entire protocol surface. The full 30-minute walk-through, including a working publisher and client in three languages, lives at [docs/tutorial/](docs/tutorial/index.md). The proposed v2 schema redesign is at [docs/spec/v0.2/wire-format.md](docs/spec/v0.2/wire-format.md).

---

## Platform notes

- **macOS.** `dns-sd` is part of the system; nothing to install. **Beacon caveat:** if you run a Saturn beacon on a laptop, keep it awake (`caffeinate -i saturn run <name>`) — the Bonjour Sleep Proxy can serve a stale TXT after the host sleeps and the published `ephemeral_key` expires. See [docs/concepts/mdns-background.md#addendum-bonjour-sleep-proxy-and-beacon-hosts](docs/concepts/mdns-background.md#addendum-bonjour-sleep-proxy-and-beacon-hosts).
- **Linux.** `sudo apt install avahi-utils`. Saturn requires Avahi ≥ 0.9-rc3; older builds are exposed to CVE-2025-68276 / 68468 / 68471. Ubuntu 24.04 LTS is patched.
- **Windows.** Install [Bonjour Print Services](https://support.apple.com/kb/DL999). If `saturn` is not on `PATH`, use `python -m saturn`.

---

## Docs · Contributing · License

- Full documentation: **[docs/](docs/index.md)** (four tabs: Home / Tutorial / Integrations / Spec).
- Contributions merged after **2026-03-20** will not be reflected in the published thesis document.
- License: see [LICENSE](LICENSE).
