# Saturn

**A zero-configuration protocol for advertising, discovering, and connecting to AI service endpoints on a local network.**

Saturn is a protocol specification, not a software package. It defines a DNS-SD service type — `_saturn._tcp.local.` — under which AI endpoints register themselves on the local network. Every device on the network discovers them automatically through Multicast DNS. No accounts. No API keys. No configuration files. The protocol provisions AI the way networks already provision printers and file shares.

The gap between AI's falling inference costs and its persistent access barriers is a protocol problem. Saturn closes that gap with infrastructure that ships on every major operating system.

---

<svg class="saturn-diagram" viewBox="0 0 820 480" xmlns="http://www.w3.org/2000/svg" width="820" height="480" style="display:block;margin:2rem auto;max-width:100%;"><defs><marker id="ag" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgb(158,158,158)"/></marker><marker id="ab" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgb(59,130,246)" opacity="0.7"/></marker></defs><rect class="diagram-bg" x="0" y="0" width="820" height="480" rx="8"/><rect class="diagram-box" x="20" y="30" width="520" height="430" rx="10" stroke-width="1.5" opacity="0.6" fill="none"/><text class="diagram-accent" x="40" y="450" font-size="13" font-style="italic">Local network</text><circle class="diagram-line" cx="120" cy="62" r="12" fill="none" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="74" x2="120" y2="110" stroke-width="1.8"/><line class="diagram-line" x1="100" y1="88" x2="140" y2="88" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="110" x2="105" y2="135" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="110" x2="135" y2="135" stroke-width="1.8"/><text class="diagram-text" x="120" y="152" text-anchor="middle" font-size="13" font-weight="700">App user</text><circle class="diagram-line" cx="340" cy="62" r="12" fill="none" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="74" x2="340" y2="110" stroke-width="1.8"/><line class="diagram-line" x1="320" y1="88" x2="360" y2="88" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="110" x2="325" y2="135" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="110" x2="355" y2="135" stroke-width="1.8"/><text class="diagram-text" x="340" y="152" text-anchor="middle" font-size="13" font-weight="700">Administrator</text><line class="diagram-line" x1="120" y1="160" x2="120" y2="200" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="132" y="185" font-size="10" opacity="0.6">owns</text><rect class="diagram-box" x="70" y="205" width="100" height="145" rx="10" stroke-width="1.5"/><rect class="diagram-accent" x="82" y="220" width="76" height="90" rx="4" opacity="0.15"/><rect class="diagram-accent" x="92" y="245" width="56" height="30" rx="4" opacity="0.3"/><text class="diagram-text" x="120" y="265" text-anchor="middle" font-size="12" font-weight="600">app</text><circle class="diagram-line" cx="120" cy="330" r="5" fill="none" stroke-width="1"/><text class="diagram-text" x="120" y="370" text-anchor="middle" font-size="11" opacity="0.6">Tablet</text><line class="diagram-line" x1="340" y1="160" x2="380" y2="295" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="395" y="230" font-size="10" opacity="0.6">configures</text><line class="diagram-line" x1="380" y1="80" x2="620" y2="80" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="500" y="72" text-anchor="middle" font-size="10" opacity="0.6">pays for</text><rect class="diagram-box" x="340" y="300" width="160" height="60" rx="6" stroke-width="1.5"/><text class="diagram-text" x="420" y="337" text-anchor="middle" font-size="15" font-weight="700">Saturn</text><text class="diagram-text" x="420" y="385" text-anchor="middle" font-size="11" opacity="0.6">Device</text><path d="M340,315 C270,290 210,290 178,295" fill="none" stroke="rgb(59,130,246)" stroke-width="2" opacity="0.7" marker-end="url(#ab)"/><text class="diagram-text" x="260" y="255" text-anchor="middle" font-size="11" font-weight="600" opacity="0.8">Announce credentials</text><text class="diagram-text" x="260" y="269" text-anchor="middle" font-size="11" font-weight="600" opacity="0.8">via mDNS</text><path class="diagram-line" d="M170,340 C230,390 300,390 340,350" fill="none" stroke-width="1.5" marker-end="url(#ag)"/><text class="diagram-text" x="255" y="410" text-anchor="middle" font-size="10" opacity="0.7">HTTP request (OpenAI-compatible)</text><path class="diagram-box" d="M650,30 Q650,10 672,12 Q682,0 705,5 Q725,-5 742,10 Q762,5 768,28 Q785,32 787,52 Q793,75 770,82 Q775,100 755,105 Q750,118 730,115 Q712,125 698,112 Q675,120 662,102 Q645,98 643,78 Q633,65 650,30 Z" fill="none" stroke-width="1.5"/><text class="diagram-text" x="715" y="45" text-anchor="middle" font-size="12" opacity="0.6">Cloud</text><rect class="diagram-box" x="690" y="56" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="62" r="2.5" opacity="0.6"/><rect class="diagram-box" x="690" y="72" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="78" r="2.5" opacity="0.6"/><rect class="diagram-box" x="690" y="88" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="94" r="2.5" opacity="0.6"/><text class="diagram-text" x="745" y="160" text-anchor="middle" font-size="13" font-weight="600">LLM provider</text><path class="diagram-line" d="M500,325 C570,325 640,240 700,110" fill="none" stroke-width="1.5" marker-end="url(#ag)"/><text class="diagram-text" x="640" y="270" font-size="10" opacity="0.7">HTTP request</text><text class="diagram-text" x="640" y="283" font-size="10" opacity="0.7">(OpenAI-compatible)</text></svg>

---

## What Saturn defines

A Saturn service is any AI endpoint advertised under the DNS-SD service type `_saturn._tcp.local.`. The protocol specifies three things and nothing else:

1. **The service type.** `_saturn._tcp.local.` — a single DNS-SD identifier, registered under the link-local mDNS scope.
2. **A TXT record schema.** Six required and optional fields that carry the endpoint URL, API format, deployment type, routing priority, and time-limited credentials.
3. **An endpoint contract.** Every advertised service exposes an OpenAI-compatible HTTP API at `/v1/health`, `/v1/models`, and `/v1/chat/completions`.

Anything that publishes a conformant advertisement is a Saturn service. Anything that resolves the service type and speaks the endpoint contract is a Saturn client. Saturn carries no shared library, no bridging layer, and no central registry — interoperability comes entirely from the specification.

---

## Why mDNS

Saturn rests on two protocols that already ship on every major operating system: Multicast DNS (mDNS, [RFC 6762](https://tools.ietf.org/html/rfc6762)) and DNS-based Service Discovery (DNS-SD, [RFC 6763](https://tools.ietf.org/html/rfc6763)). Apple's Bonjour ships natively on macOS and iOS and is available as a Windows service. Avahi is the default mDNS daemon on most Linux distributions. They interoperate.

Choosing mDNS means Saturn rides on top of the same machinery that already discovers AirPrint printers, Chromecasts, file shares, and AirPlay speakers on a typical home or campus network. There is no daemon to install, no port to forward, no infrastructure to deploy. A device that joined the network already speaks the discovery layer.

The alternatives ruled themselves out:

- **NetBIOS** — no structured metadata beyond a 15-character hostname; deprecated.
- **DLNA** — limited to media streaming; consortium dissolved.
- **WS-Discovery** — SOAP/XML payloads roughly 20× the size of a DNS query.
- **UPnP** — bundles a remote-control surface with documented security exposure.

The structural inspiration came from DHCP: a single broadcast on join, central administrator, every client benefits without per-user configuration. Saturn applies the same concentration of complexity to AI service discovery, but operates entirely in userspace on top of mDNS rather than below the IP layer.

---

## How a service announces itself

A Saturn beacon registers a standard DNS-SD record triple under `_saturn._tcp.local.`:

```
PTR  _saturn._tcp.local.  →  ollama._saturn._tcp.local.
SRV  ollama._saturn._tcp.local.  →  macbook.local. port 11434
TXT  version=1 api_type=openai deployment=local priority=1 features=chat,vision
```

The PTR record enumerates every Saturn service instance on the network. The SRV record provides the hostname and port for one instance. The TXT record carries the metadata a client needs to route and authenticate.

Beacons advertise; they do not proxy. A beacon broadcasts service metadata via mDNS and the client connects directly to the advertised endpoint over HTTP. The discovery layer and the data plane are strictly separate, which keeps beacons lightweight and prevents them from becoming a bottleneck or surveillance chokepoint.

A beacon is `local`, `cloud`, or `network`-scoped. A local beacon advertises a service running on the same host (e.g., an Ollama instance). A cloud beacon advertises a remote service (e.g., OpenRouter) and distributes ephemeral credentials so network participants can use the administrator's account without ever holding a long-lived API key.

---

## What's in a TXT record

DNS-SD encodes TXT records as `key=value` strings, one pair per string, 255 bytes max per string ([RFC 6763](https://tools.ietf.org/html/rfc6763)). Saturn defines the schema:

| Field | Required | Description |
|---|---|---|
| `version` | Yes | Protocol version (currently `1`) |
| `api_type` | Yes | Backend API format (e.g., `openai`) |
| `deployment` | Yes | One of `local`, `cloud`, or `network` |
| `priority` | Yes | Numeric routing preference; lower is preferred |
| `api_base` | Conditional | Endpoint base URL. Required when `deployment=cloud` |
| `ephemeral_key` | Conditional | Time-limited API credential. Required when `deployment=cloud` |
| `rotation_interval` | No | Key rotation period in seconds (default: `300`) |
| `features` | No | Comma-separated capability list (e.g., `chat,vision,tools`) |

`priority` mirrors the semantics of DNS SRV record priority: clients sort ascending and prefer the lowest. A lab with a local GPU server at priority 1 and an OpenRouter fallback at priority 10 gets local inference by default and cloud inference automatically when the local server is unreachable.

`ephemeral_key` is the field that makes broadcast credentials safe. Static keys fail because every mitigation — detection, rotation, revocation — acts after the damage. Saturn sidesteps that failure mode: a cloud beacon generates a short-lived credential, broadcasts it, and rotates it on a default ten-minute lifetime with a five-minute overlap. A key that expires in ten minutes is worthless by the time someone extracts it from a packet capture or commits it to a repository. The trade-off is operational — the beacon needs an active session with the cloud provider's key-provisioning API — analyzed in detail in the [Security Model](reference/security.md).

The 255-byte limit forces credential formats to be compact. JWTs from OpenRouter and DeepInfra fit. Full X.509 certificates do not. Saturn chose to carry credentials inline rather than introduce an HTTPS bootstrap endpoint, because a bootstrap endpoint would reintroduce the infrastructure dependency Saturn exists to eliminate.

---

## How a client discovers

Four steps, no user interaction:

1. **Browse.** The client queries for PTR records of type `_saturn._tcp.local.`. Every beacon on the local network responds with its instance name.
2. **Resolve.** For each instance, the client retrieves the SRV record (hostname, port) and the TXT record (metadata).
3. **Select.** The client sorts by `priority` ascending, optionally filters by `features` or `deployment`, and picks the preferred service.
4. **Connect.** For `cloud` deployments, the client uses `api_base` and attaches `ephemeral_key` as a Bearer token. For `local` and `network` deployments, the client constructs the URL from the SRV record's hostname and port (e.g., `http://macbook.local:11434/v1`).

No hardcoded URLs. No config files. No cloud accounts. The four steps replace what would otherwise be a configuration file, an environment variable, or a settings UI in every application.

---

## Three roles

The protocol decomposes participants into three responsibilities. Every design decision identifies which role bears complexity and which roles benefit.

<div class="role-cards" markdown>
<div class="role-card" markdown>

### Administrator

Deploys and configures Saturn beacons: selects backends, sets priorities, manages API credentials, monitors health. The only role that touches configuration files or credentials. One administrator absorbs the configuration burden for every other user on the network.

[**Configuration &rarr;**](configuration/service-config.md)

</div>
<div class="role-card" markdown>

### Application developer

Integrates Saturn discovery into software. Calls a function like `discover()` that returns available services with URLs and credentials already populated. No authentication logic, no configuration UI, no billing integration.

[**Protocol Reference &rarr;**](reference/protocol.md)

</div>
<div class="role-card" markdown>

### End user

Interacts with AI-powered applications without awareness that Saturn exists. Opens an app on the network, types a question, gets a response. No API key prompt, no account creation, no settings page. Performs zero configuration steps.

[**Quick Start &rarr;**](getting-started/quickstart.md)

</div>
</div>

---

## Reference implementations

Seven implementations span three languages and four mDNS libraries. None share Saturn-specific code. Interoperability comes from the specification alone — a working demonstration that Saturn is a protocol, not a package.

| Implementation | Language | mDNS Library | Role |
|---|---|---|---|
| [Python SDK](reference/python-package.md) | Python | zeroconf | Beacon + client |
| [Saturn Router](reference/router.md) | Rust | mdns-sd | Beacon (on-device, OpenWRT) |
| [AI SDK Provider](reference/ai-sdk-provider.md) | TypeScript | multicast-dns | Client |
| VLC Extension | Lua | macOS `dns-sd` CLI | Client |
| OpenCode Fork | TypeScript | multicast-dns | Client |
| Open WebUI Plugin | Python | zeroconf | Client |
| [MCP Server](reference/mcp-tools.md) | Python | zeroconf | Client |

The Python implementation (`pip install saturn-ai`) is the most complete and ships the Web UI; it is one consumer of the protocol, not the protocol itself. Any conformant advertisement from any language is a valid Saturn service.

---

## Try it from Python

A convenient way to participate in Saturn from Python — `pip install saturn-ai` — gets you the `saturn` CLI, the discovery library, and the Web UI. See [Python package — easy install](python-package.md).

---

## Read next

- **[Quick Start](getting-started/quickstart.md)** — bring up a beacon and discover it from a client.
- **[Protocol Specification](reference/protocol.md)** — the normative DNS-SD and TXT schema reference.
- **[Discovery Flow](reference/discovery.md)** — Browse → Resolve → Select → Connect in detail.
- **[Beacons & Ephemeral Keys](reference/beacons.md)** — beacon roles, key rotation, and the data-plane separation.
- **[Security Model](reference/security.md)** — threat models, broadcast exposure, and what the protocol does and doesn't protect.
