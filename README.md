# Saturn

Saturn is a protocol for zero-configuration discovery of OpenAI-compatible AI backends on a LAN, built on standard mDNS/DNS-SD records (`_saturn._tcp.local.`) with TXT metadata for priority, version, capabilities, and ephemeral credentials. It moves AI access from the application layer to the network layer: a household, lab, or office runs Saturn servers once, and every device on the network gets AI access without per-app keys, per-user subscriptions, or manual endpoint configuration.

> If you are an AI agent or LLM integrating this project, read [AGENTS.md](AGENTS.md) instead.

This repository is the artifact of a master's thesis at UC Santa Cruz (Joey Perrello, advised by Adam Smith). The thesis is in submission; citations below reference the source manuscript by line number.

---

## What the protocol asserts

Saturn is a specification, not a library. The reference implementations (Python, TypeScript, Rust) interoperate with third-party mDNS stacks because the wire format — not shared code — defines the contract. Five claims supported by the thesis follow.

1. **Cross-language interoperability emerges from the protocol, not a reference SDK.** Three consumers across three languages and four mDNS libraries (Python `zeroconf`, JS `multicast-dns`, Rust `mdns-sd`, macOS `dns-sd` CLI) interoperate with no Saturn-specific shared code. *Saturn.md:1036–1041; Table 4.1, lines 939–965.*

2. **The developer-side configuration surface collapses by ~79%.** A cognitive walkthrough comparing per-app provisioning to Saturn discovery shows 19→4 steps for the application-developer persona; 13 of the 19 eliminated steps are billing/credential scaffolding. The asymptotic form is `12 + 19N + 7M` (traditional) vs `14 + 4N + 0M` (Saturn) over `N` developers and `M` end users. *Saturn.md:1191–1224; Fig. 5.2, lines 1086–1153.*

3. **Ephemeral keys bound the dominant secret-leakage failure mode.** Meli et al. find that 81% of GitHub-leaked secrets are never revoked. A 10-minute JWT rotated every 5 minutes is dead before any scanner reaches it; the threat model shifts from internet-scale and unbounded to LAN-scoped and bounded by the rotation cycle. *Saturn.md:609–625, 1334–1344.*

4. **One TXT schema covers heterogeneous auth models.** The same record set works against Ollama (no auth), DeepInfra (static JWT), and OpenRouter (rotating ephemeral JWT) with no out-of-band configuration — evidence that the schema generalizes beyond a single vendor. *Saturn.md:1022–1031.*

5. **Network-infrastructure-layer deployment is concrete.** The Rust build cross-compiles to `mipsel-unknown-linux-musl` and runs on a GL-MT300N-V2 (128 MB RAM, MIPS32) integrated with OpenWRT/UCI/LuCI alongside DHCP. "DHCP for AI" is implemented literally. *Saturn.md:838–866.*

---

## What it does *not* claim

- **Evaluation is analytical, not empirical.** The step-reduction and threat-model arguments are derived from a single-author cognitive walkthrough and a structured threat analysis; there is no user study and no production deployment. Field evaluation is future work. *Saturn.md:1235–1250.*
- **Enterprise WiFi with AP isolation breaks Saturn.** Networks like eduroam and many guest SSIDs block client-to-client multicast — the institutional networks where the access-equity motivation matters most. A hybrid mDNS+HTTPS-fallback path is designed but not shipped. *Saturn.md:1346–1354.*
- **Multicast trust assumption.** Any device on the LAN can observe service advertisements, including ephemeral keys. Saturn trusts the network operator the way a printer protocol does; per-device authentication would void the zero-configuration property.

---

## Protocol

### Service advertisement

Services register under `_saturn._tcp.local.` with the standard DNS-SD triple (PTR, SRV, TXT). TXT fields:

| Field | Status | Description |
|---|---|---|
| `version` | required | Protocol version (`1`) |
| `api_type` | required | `openai`, `ollama`, etc. |
| `deployment` | required | `local`, `cloud`, `network` |
| `priority` | required | Numeric; lower preferred |
| `api_base` | conditional | Endpoint URL (cloud) |
| `ephemeral_key` | conditional | JWT (cloud) |
| `rotation_interval` | optional | Seconds (default 300) |
| `features` | optional | Comma-separated capabilities |

DNS-SD imposes a 255-byte limit per TXT string. JWTs fit; X.509 certificates do not — a constraint that shapes the credential design.

### Discovery

1. Browse `_saturn._tcp.local.` for PTR records.
2. Resolve SRV + TXT for each instance.
3. Sort by priority; pick the lowest healthy.
4. Use `api_base` (cloud) or construct from SRV (local).

### Endpoints

All services expose three OpenAI-compatible routes:

- `GET /v1/health`
- `GET /v1/models`
- `POST /v1/chat/completions` (SSE streaming supported)

### Beacons

A Saturn Beacon dispenses credentials without proxying inference traffic:

1. Mint a scoped JWT against a cloud provider with a 10-minute expiration.
2. Embed it in the `ephemeral_key` TXT field.
3. Rotate every 5 minutes with an overlap window where current and next keys both validate.
4. Clients read the key and call the upstream API directly.

The beacon never sees prompt or completion bytes.

---

## Reference implementations

Seven artifacts across three languages and four mDNS libraries, sharing no Saturn-specific code:

| Implementation | Language | mDNS library | Demonstrates |
|---|---|---|---|
| [`saturn/`](saturn/README.md) | Python | zeroconf | Core package: discovery, servers, beacons, CLI |
| [`ai-sdk-provider-saturn/`](ai-sdk-provider-saturn/README.md) | TypeScript | multicast-dns | AI SDK provider with circuit breaking and failover |
| [`vlc_extension/`](vlc_extension/README.md) | Lua + Python | dns-sd CLI | Bridge pattern into a non-AI-native host application |
| [`saturn-router/`](saturn-router/openwrt/README.md) | Rust | mdns-sd | Router-edge deployment on MIPS32 / 128 MB RAM |
| [OpenCode fork](https://github.com/jperrello/opencode-saturn) | TypeScript | multicast-dns | Agentic workflow with tool calls and streaming |
| [Open WebUI plugin](owui_saturn.py) | Python | zeroconf | Single-file backend swap for Open WebUI |
| [`saturn-mcp/`](saturn-mcp/README.md) | TypeScript | multicast-dns | Discovery surfaced as MCP tools |

---

## Quickstart

The lowest-friction path requires a local Ollama daemon and no API keys.

```bash
git clone https://github.com/jperrello/Saturn.git && cd Saturn
pip install -e .
```

Terminal 1 — start a Saturn-wrapped Ollama backend (assumes `ollama serve` is running on `localhost:11434`):

```bash
saturn ollama
```

Terminal 2 — discover it:

```bash
saturn discover
```

Discovery returns the advertised host, port, priority, and TXT metadata. No IP addresses or configuration files are involved.

To exercise the API end-to-end:

```bash
saturn endpoint                    # prints the URL of the highest-priority service
curl $(saturn endpoint)/v1/models
```

### Cloud backends

`saturn openrouter` and `saturn deepinfra` require provider credentials in the environment (`OPENROUTER_API_KEY`, `DEEPINFRA_API_KEY`). Copy [`.env.example`](.env.example) to `.env` and fill in the relevant key, or `export` it directly. The proxy starts even without them; `/v1/chat/completions` will return 401 from the upstream until a key is set. See `saturn/services/*.toml` for the full set of bundled service definitions.

### Router deployment

The Rust binary cross-compiles to `mipsel-unknown-linux-musl` and ships with TLS support (~2 MB). Manual install and OpenWRT integration notes are in [`saturn-router/openwrt/README.md`](saturn-router/openwrt/README.md).

### Platform notes

- **macOS.** `dns-sd` is part of the system; nothing to install.
- **Linux.** `sudo apt install avahi-utils`. Saturn requires Avahi ≥ 0.9-rc3; older builds are exposed to CVE-2025-68276 / 68468 / 68471 (remote DoS and memory corruption from crafted mDNS packets). Ubuntu 24.04 LTS is patched.
- **Windows.** Install [Bonjour Print Services](https://support.apple.com/kb/DL999). If `saturn` is not on `PATH`, use `python -m saturn`.

---

## Roles and where complexity lives

Saturn names three roles and concentrates configuration in exactly one of them.

- **Administrator** — deploys services, selects backends, sets priorities, manages credentials. The only role that touches configuration. Provisions the entire network once.
- **Application developer** — calls `discover()`; receives services with URLs and credentials populated. No auth logic, no configuration UI, no billing integration.
- **End user** — connects to the network. Nothing else.

Centralizing complexity in the administrator is what produces the asymptotic step reduction in claim 2.

---

## Evaluation summary

Cognitive walkthrough, per persona:

| Persona | Traditional | Saturn | Δ |
|---|---:|---:|---:|
| Administrator | 12 | 14 | +17% |
| Application developer | 19 | 4 | **−79%** |
| End user | 7 | 0 | **−100%** |
| **Total** | **38** | **18** | **−53%** |

At `N = 10` developers and `M = 100` end users: 902 traditional steps → 54 Saturn steps (−94%). Methodology and the threats to validity are documented in the thesis. *Saturn.md:1191–1224, 1235–1250.*

---

## Troubleshooting

```bash
dns-sd -B _saturn._tcp local.   # macOS / Bonjour browse
avahi-browse -r _saturn._tcp    # Linux / Avahi
```

If neither browse shows the server: confirm UDP 5353 is unblocked, the server log includes `Service registered`, and the host is not behind AP isolation.

---

## Contributing

PRs are welcome. The thesis is in submission; contributions merged after **2026-03-20** will not be reflected in the published document.
