# Saturn Embedded Beacon: OpenWRT Integration Plan

**Status:** Draft for Review
**Date:** January 11, 2026
**Purpose:** Extend Saturn to network infrastructure devices

---

## 1. Vision & Thesis Alignment

### The Problem This Solves

Saturn's thesis: *"One developer, zero configuration."*

The current architecture requires someone to run a beacon on their laptop or desktop. This has limitations:
- Laptops sleep, beacons disappear
- Each machine needs API keys configured
- No central point of management for households/offices

### The Solution: Network-Level Beacons

Move beacon functionality to always-on network infrastructure:

```
BEFORE: Per-Device Configuration
─────────────────────────────────────────
  Laptop          Desktop         Phone
    │                │               │
    ▼                ▼               ▼
  API Key        API Key         API Key
  Config         Config          Config
    │                │               │
    ▼                ▼               ▼
  Provider       Provider        Provider

AFTER: Network-Level Beacon
─────────────────────────────────────────
  Laptop          Desktop         Phone
    │                │               │
    └────────────────┼───────────────┘
                     │
                     ▼ (mDNS discovery)
              ┌──────────────┐
              │   OpenWRT    │
              │   Router     │
              │              │
              │ saturn-beacon│
              │ (ephemeral   │
              │  JWT issuer) │
              └──────┬───────┘
                     │
                     ▼ (HTTPS with JWT)
              ┌──────────────┐
              │   Providers  │
              │  • DeepInfra │
              │  • OpenRouter│
              └──────────────┘
```

**Key principle:** Traffic never flows through the router. The router only broadcasts credentials via mDNS. Clients call providers directly.

### Thesis Contribution

This extends Saturn from "zero-configuration AI access" to "infrastructure-level AI access":

1. **Plug-and-play**: Buy router, install package, enter API key once
2. **Network-wide**: Every device on the network gets AI access
3. **Central management**: One place to manage keys, view usage, set policies
4. **Always-on**: Routers don't sleep; beacons are always available
5. **Open ecosystem**: Works with any OpenWRT-compatible device

---

## 2. Target Hardware

### Primary Target: GL-MT300N-V2 (Mango)

| Spec | Value | Saturn Needs |
|------|-------|--------------|
| CPU | 580MHz MT7628NN (MIPS24KEc) | ✓ Sufficient for JWT gen |
| RAM | 128MB | ✓ Need ~10-15MB |
| Flash | 16MB | ✓ Need ~3MB |
| Price | ~$25 | ✓ Accessible |
| OpenWRT | Pre-installed | ✓ No flashing needed |

### Broader Compatibility

The package should work on any OpenWRT device with:
- 64MB+ RAM (128MB recommended)
- 8MB+ Flash (16MB recommended)
- MIPS, ARM, or x86 architecture
- OpenWRT 21.02 or later

This includes hundreds of routers from TP-Link, Netgear, Linksys, Ubiquiti, etc.

---

## 3. Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OpenWRT Router                               │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    LuCI Web Interface                       │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │              luci-app-saturn                          │  │    │
│  │  │                                                       │  │    │
│  │  │  • Provider configuration (API keys)                  │  │    │
│  │  │  • Beacon status dashboard                            │  │    │
│  │  │  • Priority settings                                  │  │    │
│  │  │  • Rotation interval config                           │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              │ UCI config                           │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    /etc/config/saturn                       │    │
│  │                                                             │    │
│  │  config beacon 'main'                                       │    │
│  │      option enabled '1'                                     │    │
│  │      option priority '10'                                   │    │
│  │      option rotation_interval '300'                         │    │
│  │                                                             │    │
│  │  config provider 'deepinfra'                                │    │
│  │      option enabled '1'                                     │    │
│  │      option api_key 'sk-...'                                │    │
│  │      option priority '10'                                   │    │
│  │                                                             │    │
│  │  config provider 'openrouter'                               │    │
│  │      option enabled '1'                                     │    │
│  │      option api_key 'sk-or-...'                             │    │
│  │      option priority '20'                                   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
│                              │ reads config                         │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │                    saturn-beacon                            │    │
│  │                    (Go binary)                              │    │
│  │                                                             │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │    │
│  │  │  Provider   │  │  Provider   │  │  Provider   │        │    │
│  │  │  DeepInfra  │  │ OpenRouter  │  │   (future)  │        │    │
│  │  │             │  │             │  │             │        │    │
│  │  │ JWT gen     │  │ Key rotate  │  │ Plugin API  │        │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘        │    │
│  │         │                │                │                │    │
│  │         └────────────────┼────────────────┘                │    │
│  │                          │                                  │    │
│  │                          ▼                                  │    │
│  │  ┌───────────────────────────────────────────────────┐     │    │
│  │  │              mDNS Announcer                        │     │    │
│  │  │                                                    │     │    │
│  │  │  Service: _saturn._tcp.local.                      │     │    │
│  │  │  TXT Records per provider:                         │     │    │
│  │  │    • api=DeepInfra                                 │     │    │
│  │  │    • ephemeral_key=eyJ...                          │     │    │
│  │  │    • features=ephemeral_auth                       │     │    │
│  │  │    • priority=10                                   │     │    │
│  │  └───────────────────────────────────────────────────┘     │    │
│  └────────────────────────────────────────────────────────────┘    │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │ mDNS multicast (224.0.0.251:5353)
                               ▼
            ┌──────────────────────────────────────┐
            │         Local Network Devices        │
            │                                      │
            │  • Claude Code discovers beacon      │
            │  • Receives ephemeral JWT            │
            │  • Calls provider directly           │
            └──────────────────────────────────────┘
```

### Provider Plugin Architecture

Each provider implements a simple interface:

```go
type Provider interface {
    Name() string
    Enabled() bool
    GenerateCredential() (Credential, error)
    RotationInterval() time.Duration
    TXTRecords() map[string]string
}

type Credential struct {
    Key       string    // The ephemeral key/JWT
    BaseURL   string    // API base URL
    ExpiresAt time.Time // When credential expires
}
```

Built-in providers:
1. **DeepInfra** - Uses scoped JWT API
2. **OpenRouter** - Uses provisioning key rotation
3. **Anthropic** - Direct API key (no rotation)
4. **OpenAI** - Direct API key (no rotation)

Future extensibility via config-defined providers or plugin binaries.

---

## 4. Implementation Phases

### Phase 1: Minimal Viable Beacon (Go Binary)

**Goal:** Cross-compiled Go beacon that runs on Mango

**Deliverables:**
- `saturn-beacon` Go binary (~3MB after UPX)
- Cross-compilation for MIPS (MT7628)
- Single provider support (DeepInfra)
- Config file support (JSON or UCI)
- mDNS announcement via grandcat/zeroconf

**Technical Notes:**
- Remove gopsutil dependency (process monitoring not needed)
- Use `-ldflags "-s -w"` for smaller binary
- Apply UPX compression
- Target: `GOOS=linux GOARCH=mipsle GOMIPS=softfloat`

**Testing:**
- SSH to Mango, copy binary, run manually
- Verify mDNS visible from laptop
- Verify Claude Code can discover and use credentials

### Phase 2: OpenWRT Package (.ipk)

**Goal:** Installable package with init scripts

**Deliverables:**
- OpenWRT Makefile for building package
- Init script (`/etc/init.d/saturn`)
- UCI configuration (`/etc/config/saturn`)
- Package feed configuration

**Package Structure:**
```
saturn-beacon_1.0.0-1_mipsel_24kc.ipk
├── control.tar.gz
│   ├── control          # Package metadata
│   ├── conffiles        # List of config files
│   ├── preinst          # Pre-install script
│   └── postinst         # Post-install script
└── data.tar.gz
    ├── usr/bin/saturn-beacon
    ├── etc/init.d/saturn
    └── etc/config/saturn
```

**Testing:**
- Install via `opkg install`
- Verify auto-start on boot
- Test start/stop/restart commands

### Phase 3: Multi-Provider Support

**Goal:** Extensible provider system

**Deliverables:**
- Provider plugin architecture
- OpenRouter provider implementation
- Anthropic provider implementation
- Per-provider mDNS announcements
- Per-provider rotation schedules

**UCI Config:**
```
config provider 'deepinfra'
    option enabled '1'
    option api_key 'di-...'
    option priority '10'
    option rotation_interval '300'

config provider 'openrouter'
    option enabled '1'
    option api_key 'sk-or-...'
    option priority '20'
    option rotation_interval '600'
```

### Phase 4: LuCI Web Interface

**Goal:** User-friendly configuration UI

**Deliverables:**
- `luci-app-saturn` package
- Status dashboard (active providers, last rotation, connected clients)
- Provider configuration forms
- Log viewer
- ACL permissions

**UI Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Saturn Beacon                                    [Status: ●]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Active Providers                                            │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ● DeepInfra     Priority: 10   Last Rotation: 2m ago   ││
│ │ ● OpenRouter    Priority: 20   Last Rotation: 5m ago   ││
│ │ ○ Anthropic     Not configured                          ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ [Configure Providers]  [View Logs]  [Advanced Settings]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Phase 5: Package Feed & Distribution

**Goal:** Easy installation for end users

**Deliverables:**
- Public package feed hosted on GitHub Pages
- Installation instructions
- Multi-architecture builds (MIPS, ARM, x86)
- Automated CI/CD for releases

**User Experience:**
```bash
# One-time setup
echo "src/gz saturn https://joeyperrello.github.io/saturn-openwrt" >> /etc/opkg/customfeeds.conf
opkg update

# Install
opkg install saturn-beacon luci-app-saturn

# Configure via LuCI or:
uci set saturn.deepinfra.api_key='your-key-here'
uci commit saturn
/etc/init.d/saturn restart
```

---

## 5. Relationship to Existing saturnd

The existing `saturnd` daemon (in `/saturnd/`) is designed for desktop/laptop use with:
- Full A2A agent delegation
- MCP server for Claude Code integration
- Process monitoring for agent detection
- HTTP server for Agent Cards

The OpenWRT beacon is a **subset** focused on credential distribution:

| Feature | saturnd (Desktop) | saturn-beacon (Embedded) |
|---------|-------------------|--------------------------|
| mDNS Discovery | ✓ | ✓ |
| mDNS Advertisement | ✓ | ✓ |
| Beacon Credential Cache | ✓ | ✓ (is the source) |
| Ephemeral JWT Generation | Via cache | Direct generation |
| A2A Task Delegation | ✓ | ✗ |
| MCP Server | ✓ | ✗ |
| Process Monitoring | ✓ | ✗ |
| HTTP Agent Card | ✓ | ✗ (optional) |
| Target RAM | 20-30MB | 10-15MB |
| Target Binary | 15-20MB | 2-3MB |

### Code Sharing Strategy

Extract shared code into internal packages:

```
saturnd/
├── cmd/
│   ├── saturnd/          # Full desktop daemon
│   └── saturn-beacon/    # Embedded beacon (new)
├── internal/
│   ├── beacon/           # Shared beacon logic
│   ├── discovery/        # Shared mDNS
│   ├── providers/        # NEW: Provider plugins
│   │   ├── provider.go   # Interface
│   │   ├── deepinfra.go
│   │   ├── openrouter.go
│   │   └── anthropic.go
│   ├── agents/           # Desktop only
│   ├── a2a/              # Desktop only
│   ├── http/             # Desktop only
│   └── mcp/              # Desktop only
└── openwrt/              # NEW: OpenWRT packaging
    ├── Makefile
    ├── files/
    │   ├── saturn.init
    │   └── saturn.config
    └── luci-app-saturn/
```

---

## 6. Security Considerations

### API Key Storage

UCI config files are stored in plaintext on the router's flash. Considerations:

1. **Physical access** - If someone has physical access to the router, they can extract keys. This is true of any local config.

2. **Network access** - LuCI requires authentication. API keys should never be transmitted in mDNS TXT records (only ephemeral derivatives).

3. **Ephemeral tokens** - DeepInfra JWTs expire in 10 minutes. Even if intercepted, exposure is limited.

4. **Future: Encrypted storage** - Could use OpenWRT's `uci-crypt` for encrypted config values.

### Network Trust Model

This follows the existing Saturn trust model (Layer 0 from SATURN_RINGS_INTEGRATION.md):

> "Network membership IS authentication. If you're on the local network, you're trusted."

The embedded beacon extends this model: the network administrator controls who gets AI access by controlling network access.

---

## 7. Open Questions for Joey

1. **Mango firmware version?** Need OpenWRT 21.02+ for Go compatibility. Check via LuCI: System → Software.

2. **Package feed hosting?** GitHub Pages is free and simple. Or self-hosted on your infrastructure?

3. **Multi-provider priority** - Should providers have independent priorities, or should we pick the "best" credential and only advertise one?

4. **Agent Card on embedded?** Should the embedded beacon also serve an Agent Card (making it discoverable as an A2A agent)? This would require the HTTP server.

5. **Logging strategy?** OpenWRT uses logd/logread. Should we log to syslog, or also write to a file for debugging?

---

## 8. Success Criteria

### Phase 1 Complete When:
- [ ] Go binary runs on Mango without errors
- [ ] mDNS beacon visible via `dns-sd -B _saturn._tcp`
- [ ] Claude Code on laptop discovers and uses ephemeral JWT
- [ ] RAM usage < 15MB

### Phase 2 Complete When:
- [ ] Package installs cleanly via `opkg install`
- [ ] Beacon auto-starts on boot
- [ ] Config persists across reboots
- [ ] Start/stop/restart work correctly

### Phase 3 Complete When:
- [ ] At least 3 providers supported
- [ ] Each provider can be enabled/disabled independently
- [ ] Per-provider priorities work correctly
- [ ] Rotation schedules are independent

### Phase 4 Complete When:
- [ ] LuCI page accessible under Services menu
- [ ] Can add/edit/remove providers via UI
- [ ] Status shows live beacon information
- [ ] No direct config file editing required

### Phase 5 Complete When:
- [ ] Package feed published and accessible
- [ ] Installation works on fresh OpenWRT
- [ ] Documentation complete
- [ ] At least 2 architecture builds available

---

## 9. Timeline Considerations

*No time estimates per project guidelines. Phases are ordered by dependency.*

**Dependencies:**
- Phase 2 depends on Phase 1
- Phase 3 can start parallel to Phase 2
- Phase 4 depends on Phase 2 (needs UCI config)
- Phase 5 depends on Phases 1-4

**Suggested approach:** Complete Phase 1 as proof-of-concept, then evaluate scope for remaining phases.
