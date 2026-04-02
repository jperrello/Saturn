# Saturn

**Zero-configuration AI service discovery for every device on your network.**

Saturn provisions AI the way networks already provision printers and file shares: through [Multicast DNS](https://tools.ietf.org/html/rfc6762) and [DNS-based Service Discovery](https://tools.ietf.org/html/rfc6763). A Saturn device announces AI endpoints under the service type `_saturn._tcp.local.`, and every device on the network discovers them automatically — no accounts, no API keys, no configuration files.

The gap between AI's falling inference costs and its persistent access barriers is a protocol problem. Saturn closes that gap with existing network infrastructure.

---

<svg class="saturn-diagram" viewBox="0 0 820 480" xmlns="http://www.w3.org/2000/svg" width="820" height="480" style="display:block;margin:2rem auto;max-width:100%;"><defs><marker id="ag" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgb(158,158,158)"/></marker><marker id="ab" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="rgb(59,130,246)" opacity="0.7"/></marker></defs><rect class="diagram-bg" x="0" y="0" width="820" height="480" rx="8"/><rect class="diagram-box" x="20" y="30" width="520" height="430" rx="10" stroke-width="1.5" opacity="0.6" fill="none"/><text class="diagram-accent" x="40" y="450" font-size="13" font-style="italic">Local network</text><circle class="diagram-line" cx="120" cy="62" r="12" fill="none" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="74" x2="120" y2="110" stroke-width="1.8"/><line class="diagram-line" x1="100" y1="88" x2="140" y2="88" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="110" x2="105" y2="135" stroke-width="1.8"/><line class="diagram-line" x1="120" y1="110" x2="135" y2="135" stroke-width="1.8"/><text class="diagram-text" x="120" y="152" text-anchor="middle" font-size="13" font-weight="700">App user</text><circle class="diagram-line" cx="340" cy="62" r="12" fill="none" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="74" x2="340" y2="110" stroke-width="1.8"/><line class="diagram-line" x1="320" y1="88" x2="360" y2="88" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="110" x2="325" y2="135" stroke-width="1.8"/><line class="diagram-line" x1="340" y1="110" x2="355" y2="135" stroke-width="1.8"/><text class="diagram-text" x="340" y="152" text-anchor="middle" font-size="13" font-weight="700">Administrator</text><line class="diagram-line" x1="120" y1="160" x2="120" y2="200" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="132" y="185" font-size="10" opacity="0.6">owns</text><rect class="diagram-box" x="70" y="205" width="100" height="145" rx="10" stroke-width="1.5"/><rect class="diagram-accent" x="82" y="220" width="76" height="90" rx="4" opacity="0.15"/><rect class="diagram-accent" x="92" y="245" width="56" height="30" rx="4" opacity="0.3"/><text class="diagram-text" x="120" y="265" text-anchor="middle" font-size="12" font-weight="600">app</text><circle class="diagram-line" cx="120" cy="330" r="5" fill="none" stroke-width="1"/><text class="diagram-text" x="120" y="370" text-anchor="middle" font-size="11" opacity="0.6">Tablet</text><line class="diagram-line" x1="340" y1="160" x2="380" y2="295" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="395" y="230" font-size="10" opacity="0.6">configures</text><line class="diagram-line" x1="380" y1="80" x2="620" y2="80" stroke-width="1.2" stroke-dasharray="4,3"/><text class="diagram-text" x="500" y="72" text-anchor="middle" font-size="10" opacity="0.6">pays for</text><rect class="diagram-box" x="340" y="300" width="160" height="60" rx="6" stroke-width="1.5"/><text class="diagram-text" x="420" y="337" text-anchor="middle" font-size="15" font-weight="700">Saturn</text><text class="diagram-text" x="420" y="385" text-anchor="middle" font-size="11" opacity="0.6">Device</text><path d="M340,315 C270,290 210,290 178,295" fill="none" stroke="rgb(59,130,246)" stroke-width="2" opacity="0.7" marker-end="url(#ab)"/><text class="diagram-text" x="260" y="255" text-anchor="middle" font-size="11" font-weight="600" opacity="0.8">Announce credentials</text><text class="diagram-text" x="260" y="269" text-anchor="middle" font-size="11" font-weight="600" opacity="0.8">via mDNS</text><path class="diagram-line" d="M170,340 C230,390 300,390 340,350" fill="none" stroke-width="1.5" marker-end="url(#ag)"/><text class="diagram-text" x="255" y="410" text-anchor="middle" font-size="10" opacity="0.7">HTTP request (OpenAI-compatible)</text><path class="diagram-box" d="M650,30 Q650,10 672,12 Q682,0 705,5 Q725,-5 742,10 Q762,5 768,28 Q785,32 787,52 Q793,75 770,82 Q775,100 755,105 Q750,118 730,115 Q712,125 698,112 Q675,120 662,102 Q645,98 643,78 Q633,65 650,30 Z" fill="none" stroke-width="1.5"/><text class="diagram-text" x="715" y="45" text-anchor="middle" font-size="12" opacity="0.6">Cloud</text><rect class="diagram-box" x="690" y="56" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="62" r="2.5" opacity="0.6"/><rect class="diagram-box" x="690" y="72" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="78" r="2.5" opacity="0.6"/><rect class="diagram-box" x="690" y="88" width="50" height="12" rx="2" stroke-width="1"/><circle class="diagram-accent" cx="732" cy="94" r="2.5" opacity="0.6"/><text class="diagram-text" x="745" y="160" text-anchor="middle" font-size="13" font-weight="600">LLM provider</text><path class="diagram-line" d="M500,325 C570,325 640,240 700,110" fill="none" stroke-width="1.5" marker-end="url(#ag)"/><text class="diagram-text" x="640" y="270" font-size="10" opacity="0.7">HTTP request</text><text class="diagram-text" x="640" y="283" font-size="10" opacity="0.7">(OpenAI-compatible)</text></svg>

---

## How it works

**1. Announce** — An administrator runs a Saturn beacon that broadcasts AI service metadata on the local network via mDNS. TXT records carry the endpoint URL, API type, priority, and time-limited credentials.

**2. Discover** — Any application on the network resolves these records automatically. No hardcoded URLs, no config files, no cloud accounts.

**3. Connect** — The client selects the highest-priority service and talks to it over standard OpenAI-compatible HTTP. If multiple services exist, Saturn routes to the best one with automatic failover.

Beacons broadcast metadata but never proxy API traffic. Clients connect directly to endpoints, keeping beacons lightweight and eliminating them as a bottleneck or surveillance chokepoint.

---

## Who is Saturn for?

<div class="role-cards" markdown>
<div class="role-card" markdown>

### End Users

Use AI-powered applications on your local network with no setup. Saturn handles discovery behind the scenes — you never touch a config file, create an account, or enter an API key.

[**Quick Start &rarr;**](getting-started/quickstart.md)

</div>
<div class="role-card" markdown>

### Administrators

Deploy Saturn beacons, manage API credentials, set routing priorities, and control budgets. One device serves your entire household, lab, or team.

[**Configuration &rarr;**](configuration/service-config.md)

</div>
<div class="role-card" markdown>

### Application Developers

Integrate Saturn discovery into your software. Call `discover()` to get services with URLs and credentials pre-populated. SDKs in Python, Rust, and TypeScript.

[**Reference &rarr;**](reference/protocol.md)

</div>
</div>

---

## Why Saturn exists

The dominant AI access model creates barriers that scale with users. A student needing three AI capabilities from three providers must manage three subscriptions, three API keys, and three billing relationships. Research shows students from lower socioeconomic backgrounds interact less frequently with AI tools as a result.

Universities already provision shared resources — printers, file shares, licensed software — through zero-configuration network protocols. There was no equivalent for AI services. Saturn fills that gap.

An institution deploys a Saturn beacon, funds a token budget with a cloud provider, and every device joining the network discovers the service automatically. Students pay nothing. The institution pays only for tokens consumed, not seats licensed.

---

## Install

Saturn's Python reference implementation:

```bash
pip install saturn-ai
```

This gives you the `saturn` CLI, the discovery library, and the [Web UI](web-ui/overview.md). Other implementations (Rust router, TypeScript AI SDK provider, Lua VLC extension) live in their own packages — see the [Reference](reference/protocol.md) section.

---

## Saturn is a protocol, not a package

Seven implementations span three languages and four mDNS libraries. None share Saturn-specific code. Interoperability comes from the protocol specification: standard DNS-SD records on `_saturn._tcp.local.`, a fixed TXT schema, and OpenAI-compatible HTTP endpoints.

| Implementation | Language | mDNS Library |
|---|---|---|
| Python SDK | Python | zeroconf |
| Saturn Router | Rust | mdns-sd |
| AI SDK Provider | TypeScript | multicast-dns |
| VLC Extension | Lua | macOS dns-sd CLI |
| OpenCode Fork | TypeScript | multicast-dns |
| Open WebUI Plugin | Python | zeroconf |
| MCP Server | Python | zeroconf |
