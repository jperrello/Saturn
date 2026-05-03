# Saturn — landing copy

Three discrete artifacts. All claims sourced from `SATURN_CONTEXT.md` / `Saturn.md`; no invention.

---

## 1. GitHub repo "About" field

```
Zero-configuration discovery for OpenAI-compatible AI backends on a LAN — mDNS/DNS-SD service type _saturn._tcp.local. with TXT-encoded priority, capabilities, and ephemeral credentials. UCSC master's thesis artifact.
```

---

## 2. Above-the-fold hero

```
# AI access at the network layer.

### Saturn is a protocol for zero-configuration discovery of OpenAI-compatible AI backends on a LAN.

Run a Saturn server once on your home, lab, or office network. Every device on
that network gets AI access — no per-app keys, no per-user subscriptions, no
manual endpoint configuration. The protocol is mDNS/DNS-SD: the same
mechanism your laptop already uses to find printers and AirPlay receivers.
Three reference implementations across Python, TypeScript, and Rust
interoperate with no Saturn-specific shared code, and the Rust build runs on
a $20 OpenWRT router alongside DHCP.

    git clone https://github.com/jperrello/Saturn && cd Saturn
    pip install -e . && saturn ollama
```

---

## 3. Social / share card copy

Three variants, each ≤ 280 characters.

### (a) ML systems researchers

```
Saturn: zero-configuration AI service discovery on a LAN, via mDNS/DNS-SD. Cognitive walkthrough shows app-developer config drops 19→4 steps (-79%), asymptotic 12+19N+7M → 14+4N. Three languages, four mDNS libraries, no shared SDK. UCSC thesis artifact.
```

### (b) Self-hosted / homelab

```
You're already running Ollama. Saturn announces it on your LAN via mDNS, the same way your printer does — every device on the network finds it automatically. No API keys, no config files, no per-app setup. Cross-compiles to a $20 OpenWRT router.
```

### (c) IT admins / network ops

```
Saturn moves AI endpoint provisioning to the network layer. One admin registers backends; clients discover via _saturn._tcp.local. and route by priority. Cloud credentials ship as 10-min ephemeral JWTs in TXT records — leaked keys expire before scanners reach them.
```
