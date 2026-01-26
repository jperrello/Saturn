# Saturn Agent Daemon (saturnd)

Zero-configuration AI agent discovery and credential injection for local networks.

## Overview

The Saturn Agent Daemon enables AI agents (like Claude Code) running on different machines to automatically discover each other and collaborate—without any manual configuration. It also provides automatic API credential injection from Saturn beacons on the network.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Saturn Network Architecture                          │
│                                                                              │
│  DESKTOP                                LAPTOP                               │
│  ────────                               ──────                               │
│  ┌─────────────────┐                    ┌─────────────────┐                 │
│  │  Claude Code    │                    │  Claude Code    │                 │
│  │  (MCP Client)   │                    │  (MCP Client)   │                 │
│  └────────┬────────┘                    └────────┬────────┘                 │
│           │ stdio                                │ stdio                     │
│           ▼                                      ▼                           │
│  ┌─────────────────┐                    ┌─────────────────┐                 │
│  │    saturnd      │◄────── mDNS ──────►│    saturnd      │                 │
│  │                 │   _saturn._tcp     │                 │                 │
│  │  • MCP Server   │                    │  • MCP Server   │                 │
│  │  • HTTP :7827   │                    │  • HTTP :7827   │                 │
│  │  • A2A Tasks    │                    │  • A2A Tasks    │                 │
│  └─────────────────┘                    └─────────────────┘                 │
│                                                                              │
│                        OPENWRT ROUTER                                        │
│                    ┌─────────────────────┐                                  │
│                    │      saturn         │                                  │
│                    │   (mDNS credential  │◄──────────────────────────┐      │
│                    │    broadcaster)     │                           │      │
│                    └─────────────────────┘                           │      │
│                              │                                       │      │
│                              │ Ephemeral API Key                     │      │
│                              ▼                                       │      │
│                    ┌─────────────────────┐                           │      │
│                    │     OpenRouter      │    (or other providers)   │      │
│                    └─────────────────────┘───────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Binaries

This project produces two binaries:

| Binary | Purpose | Target |
|--------|---------|--------|
| `saturnd` | Full daemon with MCP server, HTTP server, A2A task handling | Desktop/Laptop/Server |
| `saturn` | Minimal mDNS beacon for credential broadcasting | OpenWRT routers, embedded devices |

## Building

```bash
cd saturnd

# Build the main daemon
go build -o saturnd ./cmd/saturnd

# Build the embedded beacon
go build -o saturn ./cmd/saturn

# Cross-compile beacon for OpenWRT (MIPS)
CGO_ENABLED=0 GOOS=linux GOARCH=mipsle GOMIPS=softfloat \
  go build -ldflags "-s -w" -o saturn-mips ./cmd/saturn
```

## Quick Start

### Running the Daemon

```bash
# Start the daemon (default port 7827)
./saturnd

# With verbose logging
./saturnd --verbose

# Custom port
./saturnd --port 8080
```

### Running as MCP Server (for Claude Code)

Configure Claude Code to use Saturn as an MCP server:

```json
{
  "mcpServers": {
    "saturn": {
      "command": "saturnd",
      "args": ["mcp"]
    }
  }
}
```

Or set the environment variable:
```bash
SATURN_MCP_MODE=1 ./saturnd
```

### Running the Beacon (on a router)

```bash
# With environment variable
OPENROUTER_PROVISIONING_KEY=your-key-here ./saturn

# With config file
./saturn --config=/etc/saturn/beacon.json

# With CLI flags
./saturn --api-key=your-key --priority=10 --limit=5.00
```

## Features

### mDNS Discovery & Advertisement

- Discovers Saturn services on `_saturn._tcp.local.`
- Automatically finds beacons (credential sources) and agents (task targets)
- Advertises this machine as a Saturn agent with A2A-compatible Agent Card

### A2A Agent Cards

Serves an A2A-compliant Agent Card at `/.well-known/agent-card.json`:

```json
{
  "name": "hostname-saturn-agent",
  "description": "Saturn Agent Daemon - Zero-configuration AI service discovery",
  "version": "1.0.0",
  "url": "http://192.168.1.100:7827",
  "supportedInterfaces": [
    {"protocol": "a2a/1.0", "url": "http://192.168.1.100:7827/a2a"},
    {"protocol": "http", "url": "http://192.168.1.100:7827"}
  ],
  "capabilities": {"streaming": true, "pushNotifications": false},
  "skills": [],
  "authentication": {"schemes": ["none"]}
}
```

### MCP Tools

The MCP server provides four tools for Claude Code integration:

| Tool | Description |
|------|-------------|
| `discover_agents` | Find AI agents on the local network via mDNS |
| `delegate_task` | Send a task to a remote agent via A2A protocol |
| `get_credentials` | Retrieve API credentials from Saturn beacons |
| `get_agent_status` | Get status of local daemon and detected agents |

### HTTP API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | A2A Agent Card |
| `/v1/credentials` | GET | Best available API credentials |
| `/v1/health` | GET | Daemon health and statistics |
| `/v1/agents` | GET | List discovered agents |
| `/a2a/tasks` | POST | Submit A2A task (sync) |
| `/a2a/tasks/async` | POST | Submit A2A task (async) |
| `/a2a/tasks?id=` | GET | Get async task status |

### Beacon Credential Caching

- Caches ephemeral credentials from Saturn beacons
- Priority-based selection (lower = higher priority)
- Automatic expiration tracking
- Support for multiple providers

### AI Agent Process Monitoring

Detects running AI agents via process monitoring:
- Claude Code
- Aider
- Cursor
- VS Code (with AI extensions)
- OpenAI Codex
- Sourcegraph Amp

## Architecture

```
saturnd/
├── cmd/
│   ├── saturnd/              # Main daemon entry point
│   │   └── main.go
│   └── saturn/               # Embedded beacon for routers
│       ├── main.go
│       ├── README.md
│       └── beacon.example.json
├── internal/
│   ├── a2a/                  # A2A protocol implementation
│   │   ├── client.go         # A2A client for task delegation
│   │   ├── executor.go       # Task execution (spawns Claude)
│   │   ├── handler.go        # HTTP handlers for /a2a/* endpoints
│   │   └── types.go          # Task, Message, Result types
│   ├── agents/               # AI agent detection
│   │   └── monitor.go        # Process monitoring with gopsutil
│   ├── beacon/               # Credential caching
│   │   ├── cache.go          # Thread-safe credential cache
│   │   └── types.go          # Credential types, provider URLs
│   ├── discovery/            # mDNS discovery & advertisement
│   │   ├── advertiser.go     # Agent Card generation, mDNS registration
│   │   └── discovery.go      # Service browsing, TXT record parsing
│   ├── http/                 # HTTP server
│   │   ├── handlers.go       # Endpoint implementations
│   │   └── server.go         # Server setup, middleware
│   ├── mcp/                  # MCP protocol implementation
│   │   ├── protocol.go       # JSON-RPC 2.0 types
│   │   ├── server.go         # MCP server (stdio transport)
│   │   └── tools.go          # Tool definitions and handlers
│   └── providers/            # API provider abstraction
│       ├── openrouter.go     # OpenRouter ephemeral key generation
│       └── provider.go       # Provider interface
├── openwrt/                  # OpenWRT package
│   ├── files/
│   │   ├── saturn.config     # UCI configuration template
│   │   └── saturn.init       # procd init script
│   ├── Makefile              # OpenWRT package Makefile
│   └── README.md             # OpenWRT-specific documentation
├── scripts/                  # System service installation
│   ├── com.saturn.daemon.plist   # macOS launchd
│   ├── install.ps1           # Windows PowerShell installer
│   ├── install.sh            # Linux/macOS installer
│   ├── saturnd.service       # systemd unit file
│   └── uninstall.sh          # Uninstaller
├── go.mod
├── go.sum
└── README.md
```

## Installation

### Linux (systemd)

```bash
# Run installer
sudo ./scripts/install.sh

# Or manually:
sudo cp saturnd /usr/local/bin/
sudo cp scripts/saturnd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now saturnd
```

### macOS (launchd)

```bash
sudo ./scripts/install.sh

# Or manually:
sudo cp saturnd /usr/local/bin/
sudo cp scripts/com.saturn.daemon.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.saturn.daemon.plist
```

### Windows (Service)

```powershell
# Run as Administrator
.\scripts\install.ps1
```

### OpenWRT

See [openwrt/README.md](openwrt/README.md) for detailed instructions.

Quick start:
```bash
# Copy beacon to router
scp saturn-mips root@192.168.1.1:/tmp/saturn

# SSH and run
ssh root@192.168.1.1
OPENROUTER_PROVISIONING_KEY=your-key /tmp/saturn
```

## Configuration

### Beacon Configuration (JSON)

Create a config file at `/etc/saturn/beacon.json`:

```json
{
  "name": "my-beacon",
  "priority": 10,
  "provider": {
    "type": "openrouter",
    "api_key": "your-openrouter-provisioning-key",
    "rotation_seconds": 300,
    "expires_seconds": 600,
    "spending_limit": 0
  }
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_PROVISIONING_KEY` | OpenRouter provisioning key for beacon |
| `SATURN_MCP_MODE` | Set to "1" to run as MCP server |

### CLI Flags

**saturnd:**
```
--port          HTTP server port (default: 7827)
--mcp-port      MCP server port (default: 7828)
--verbose       Enable verbose logging
```

**saturn:**
```
--config        Path to config file (default: /etc/saturn/beacon.json)
--api-key       API key (overrides config)
--priority      Service priority (overrides config)
--limit         Spending limit per key in USD (default: 0 = no limit)
```

## Supported Providers

Currently implemented:
- **OpenRouter** - Full support with ephemeral key generation and automatic cleanup

Provider base URLs recognized:
- OpenRouter: `https://openrouter.ai/api/v1`
- DeepInfra: `https://api.deepinfra.com/v1/openai`
- OpenAI: `https://api.openai.com/v1`
- Anthropic: `https://api.anthropic.com/v1`
- Together: `https://api.together.xyz/v1`
- Groq: `https://api.groq.com/openai/v1`
- Fireworks: `https://api.fireworks.ai/inference/v1`
- Perplexity: `https://api.perplexity.ai`
- Mistral: `https://api.mistral.ai/v1`
- Cohere: `https://api.cohere.ai/v1`

## Dependencies

- [grandcat/zeroconf](https://github.com/grandcat/zeroconf) - Pure Go mDNS/DNS-SD
- [shirou/gopsutil](https://github.com/shirou/gopsutil) - Cross-platform process monitoring

## Related Documentation

- [Architecture](../research/A2A_MCP/ARCHITECTURE.md) - System architecture and design decisions
- [Implementation Plan](../research/A2A_MCP/IMPLEMENTATION_PLAN.md) - Detailed specifications
- [OpenWRT Beacon Plan](../research/A2A_MCP/OPENWRT_BEACON_PLAN.md) - Embedded beacon strategy

## Work Tracking

Development is tracked in beads. Run `bd ready` to see available work:

```bash
bd ready              # Show available tasks
bd show <id>          # View task details
bd list --status=open # All open issues
```

## License

MIT License - See LICENSE file in repository root.
