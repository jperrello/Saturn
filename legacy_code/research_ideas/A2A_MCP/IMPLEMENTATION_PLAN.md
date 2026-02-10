# Saturn Agent Daemon: Complete Implementation Plan

**Document Version:** 1.0
**Date:** January 10, 2026
**Authors:** Joey Perrello (human), Claude (AI)
**Status:** Approved for Implementation

This document provides the complete technical specification for implementing the Saturn Agent Daemon. Agents working on this implementation must treat this document as the authoritative source of truth. The architecture diagram in `ARCHITECTURE.md` (same directory) provides the visual reference that all implementation must conform to.

---

## Table of Contents

1. Background and Motivation
2. Protocol Foundations
3. Saturn Daemon Architecture
4. Component Specifications
5. Implementation Details
6. Testing Strategy
7. Future Work: ANS Integration

---

## 1. Background and Motivation

### 1.1 The Problem Saturn Solves

Saturn is Joey Perrello's master's project at UC Santa Cruz, developed under advisors Adam and Ram. The project addresses the API key configuration burden that plagues AI tooling. As documented in the Saturn Rings Integration research (located at `research/rings/SATURN_RINGS_INTEGRATION.md` lines 27-39):

Most AI-powered tools require users to sign up for API access, generate API keys, configure keys in each tool they use, manage billing separately per tool, and repeat this for every machine they work on. This creates an N×M problem where N developers multiplied by M tools equals N×M configurations. Saturn inverts this model. Before Saturn, every client configures how to reach every provider. After Saturn, providers advertise themselves and clients discover what is available.

### 1.2 The Multi-Agent Extension

This implementation extends Saturn from inference discovery to agent-to-agent communication. The goal is enabling Claude Code on one machine to delegate tasks to Claude Code on another machine, with zero manual configuration required. The user starts Claude Code on their desktop and laptop, and the two instances can automatically discover each other and collaborate.

### 1.3 Why This Matters for Saturn's Thesis

The Saturn thesis centers on zero-configuration. The phrase that guides all design decisions is: "one developer, zero configuration." This implementation must maintain that principle. The daemon runs as a system service, starts automatically on boot, and requires no per-session configuration from users. The MCP server integration requires a one-time configuration in Claude Code's settings file, after which all future sessions automatically benefit from agent discovery and credential injection.

---

## 2. Protocol Foundations

This section documents the protocols that Saturn integrates. Each subsection includes the authoritative source, direct quotes from specifications, and technical details relevant to implementation.

### 2.1 mDNS and DNS-SD

**Authoritative Source:** RFC 6763 "DNS-Based Service Discovery"
**URL:** https://www.rfc-editor.org/rfc/rfc6763.html

mDNS (Multicast DNS) allows devices to resolve hostnames without a central DNS server. When a laptop looks for `adams-workstation.local`, it sends a multicast query on the local network, and Adam's workstation responds directly. DNS-SD (DNS Service Discovery) builds on mDNS to advertise services.

From RFC 6763 Section 4: "The Service portion of the Service Instance Name consists of a pair of DNS labels, following the convention already established for SRV records. The first label of the pair is an underscore character followed by the Service Name. For applications using TCP, the second label is '_tcp'."

The service name can be up to 15 characters (plus the underscore prefix, making 16 bytes total). Saturn uses `_saturn` as the service name, making the full service type `_saturn._tcp.local.` This is already established in the existing codebase at `saturn/discovery.py` line 68:

```python
SERVICE_TYPE = "_saturn._tcp.local."
```

TXT records carry additional service metadata. RFC 6763 Section 6 specifies the format: "DNS TXT record can be up to 65535 bytes long. However, each constituent string is limited to 255 bytes." Each key-value pair is encoded as a single string in the format `key=value`. Saturn's existing beacon implementation (documented in `beacons/beacon_explained.md` lines 246-253) uses TXT records to advertise ephemeral API keys:

```python
properties={
    'version': '1.0',
    'api': 'DeepInfra',
    'priority': str(self.priority),
    'ephemeral_key': token,
    'rotation_interval': str(self.jwt_manager.rotation_interval),
    'features': 'ephemeral_auth'
}
```

The daemon extends this pattern by adding agent-specific TXT records:

```
agent=true                              # Indicates this is an agent, not just inference
agent_card=http://192.168.1.50:7827/.well-known/agent-card.json
protocols=a2a,mcp                       # Supported communication protocols
saturn=2.0                              # Saturn protocol version
```

### 2.2 The A2A Protocol

**Authoritative Source:** A2A Protocol Specification
**URL:** https://a2a-protocol.org/latest/specification/
**GitHub:** https://github.com/a2aproject/A2A

The Agent-to-Agent (A2A) protocol is an open standard contributed by Google to the Linux Foundation. It enables communication and interoperability between AI agents. The specification was announced in April 2025 and has been adopted by major AI platforms.

From the A2A specification: "The A2A protocol is built on familiar web technologies: it uses JSON-RPC 2.0 over HTTP(S) as the core communication method. In non-engineer speak, that means agents send each other JSON-formatted messages via standard web calls."

The protocol has three primary bindings: JSON-RPC 2.0 over HTTPS, gRPC over HTTP/2 with TLS, and HTTP+JSON/REST using standard HTTP methods. For Saturn's local network use case, HTTPS is not required since network membership implies trust (as documented in `research/rings/SATURN_RINGS_INTEGRATION.md` lines 196-200).

#### 2.2.1 Agent Cards

The Agent Card is the central discovery mechanism in A2A. From the specification Section 4.4.1: "The Agent Card is a self-describing manifest for an agent providing metadata about identity, capabilities, skills, communication methods, and security requirements."

Agent Cards are hosted at a well-known URI. The specification states: "Clients can find Agent Cards through Well-Known URI: Accessing `https://{server_domain}/.well-known/agent-card.json`"

The well-known URI convention is defined by RFC 8615 "Well-Known Uniform Resource Identifiers (URIs)" published May 2019. The IANA registry of well-known URIs is maintained at https://www.iana.org/assignments/well-known-uris. Note that the A2A specification uses `agent-card.json` (with a hyphen), not `agent.json`.

The Agent Card schema requires these fields according to the specification:

```json
{
  "name": "string - Human-readable agent identifier",
  "description": "string - Purpose explanation",
  "version": "string - Agent version number",
  "url": "string - Base URL for the agent",
  "supportedInterfaces": [
    {
      "protocol": "string - Protocol identifier (a2a/1.0, http, grpc)",
      "url": "string - URL for this protocol"
    }
  ],
  "capabilities": {
    "streaming": "boolean - Supports streaming responses",
    "pushNotifications": "boolean - Supports push notifications"
  },
  "defaultInputModes": ["string - Supported input media types"],
  "defaultOutputModes": ["string - Supported output media types"],
  "skills": [
    {
      "id": "string - Unique skill identifier",
      "name": "string - Human-readable skill name",
      "description": "string - What this skill does"
    }
  ],
  "authentication": {
    "schemes": ["string - Required auth schemes (none, Bearer, ApiKey, etc.)"]
  }
}
```

For Saturn's implementation, the authentication scheme is `none` for local network use, matching the Layer 0 trust model described in the Rings Integration document.

#### 2.2.2 A2A Discovery Gap

The A2A specification defines three discovery methods: Well-Known URI (HTTP GET to a known domain), Curated Registries (centralized catalog), and Direct Configuration (hardcoded details). Critically, the specification states there is "no mention of local network discovery methods such as mDNS."

This is Saturn's contribution to the A2A ecosystem. Saturn provides the local network discovery layer that A2A lacks. Agents advertise via mDNS, clients discover via DNS-SD, and then communication proceeds using the standard A2A protocol. This is the architectural pattern described in `research/rings/SATURN_RINGS_INTEGRATION.md` line 227: "Saturn introduces a new DNS-SD service type for MCP-compatible AI services."

#### 2.2.3 A2A Task Delegation

A2A uses Task objects to represent work delegated between agents. The specification describes the flow: "The client agent simply fetches this card (directly or via a registry) to see who can do what and how to connect. The server will perceive this Message as a Task to be completed."

A Task contains a user message, optional context, and metadata about the requested work. The server agent processes the task and returns results. This maps directly to the delegation flow shown in the architecture diagram: Claude Code calls an MCP tool to delegate a task, Saturn daemon translates this to an A2A Task, sends it to the remote Saturn daemon, which spawns Claude Code to execute it.

### 2.3 The Model Context Protocol (MCP)

**Authoritative Source:** MCP Specification
**URL:** https://modelcontextprotocol.io/specification/2025-11-25
**Background:** https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/

The Model Context Protocol is an open standard introduced by Anthropic in November 2024 that standardizes how AI systems integrate with external tools and data sources. In December 2025, Anthropic donated MCP to the Agentic AI Foundation under the Linux Foundation.

From the Wikipedia article on MCP: "The Model Context Protocol (MCP) is an open standard and open-source framework introduced by Anthropic in November 2024 to standardize the way artificial intelligence (AI) systems like large language models (LLMs) integrate and share data with external tools, systems, and data sources."

MCP uses JSON-RPC 2.0 as its communication protocol. The November 2025 spec release added support for tool calling in sampling requests, server-side agent loops, and parallel tool calls. These features are relevant to Saturn's implementation because they enable the MCP server to orchestrate complex multi-step operations.

#### 2.3.1 MCP Server Architecture

An MCP server exposes three types of primitives: Tools (functions the LLM can call), Resources (data the LLM can read), and Prompts (templates for common interactions). For Saturn, the primary integration is through Tools.

The MCP server communicates with Claude Code via stdio (standard input/output). When Claude Code starts, it spawns the MCP server process and communicates by writing JSON-RPC messages to its stdin and reading responses from its stdout. This is the transport mechanism used by all Claude Code MCP servers.

#### 2.3.2 Saturn's MCP Tools

The Saturn MCP server exposes four tools:

**Tool 1: discover_agents**

This tool queries the local network for Saturn-enabled agents. It triggers an mDNS browse, collects Agent Cards from discovered services, and returns a list of available agents with their capabilities.

```json
{
  "name": "discover_agents",
  "description": "Discover AI agents on the local network via Saturn",
  "inputSchema": {
    "type": "object",
    "properties": {
      "skill_filter": {
        "type": "string",
        "description": "Optional skill to filter agents by (e.g., 'research', 'code_review')"
      },
      "timeout_seconds": {
        "type": "number",
        "description": "Discovery timeout in seconds (default: 3)"
      }
    }
  }
}
```

**Tool 2: delegate_task**

This tool sends a task to a remote agent. It takes the target agent name, the task description, and optional context. The Saturn daemon translates this into an A2A Task object and sends it to the remote agent's Saturn daemon.

```json
{
  "name": "delegate_task",
  "description": "Delegate a task to a remote agent discovered via Saturn",
  "inputSchema": {
    "type": "object",
    "properties": {
      "agent_name": {
        "type": "string",
        "description": "Name of the target agent (from discover_agents)"
      },
      "task": {
        "type": "string",
        "description": "Description of the task to delegate"
      },
      "context": {
        "type": "string",
        "description": "Optional context or files to include"
      },
      "wait_for_result": {
        "type": "boolean",
        "description": "Whether to wait for the task to complete (default: true)"
      }
    },
    "required": ["agent_name", "task"]
  }
}
```

**Tool 3: get_credentials**

This tool retrieves API credentials from beacons on the local network. It returns the best available credential based on priority, which Claude Code can then use for inference requests.

```json
{
  "name": "get_credentials",
  "description": "Get API credentials from Saturn beacons on the network",
  "inputSchema": {
    "type": "object",
    "properties": {
      "provider": {
        "type": "string",
        "description": "Optional provider filter (e.g., 'DeepInfra', 'OpenRouter')"
      }
    }
  }
}
```

The response includes the API key, base URL, provider name, and expiration time:

```json
{
  "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "base_url": "https://api.deepinfra.com/v1/openai",
  "provider": "DeepInfra",
  "expires_in_seconds": 285
}
```

**Tool 4: get_agent_status**

This tool returns information about the local Saturn daemon and detected agents on this machine.

```json
{
  "name": "get_agent_status",
  "description": "Get status of the local Saturn daemon and detected agents",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

---

## 3. Saturn Daemon Architecture

The Saturn daemon (named `saturnd`) is a Go binary that runs as a system service. It provides four integrated subsystems: mDNS discovery, mDNS advertisement, an HTTP server, and an MCP server.

### 3.1 Why Go

Go was chosen for several reasons documented during the design conversation:

Memory overhead is a concern for daemons that run continuously. A Python daemon using zeroconf and aiohttp typically uses 30-50 MB of RAM. A Go binary uses 10-20 MB. The existing mDNSResponder daemon on macOS uses 5-10 MB, and avahi-daemon on Linux uses 3-8 MB, both written in C. Go provides a middle ground: better memory efficiency than Python without the complexity of C.

Cross-platform compilation is straightforward in Go. A single codebase compiles to native binaries for Linux, macOS, and Windows without modification. This matches Saturn's goal of working on any developer's machine.

The gopsutil library (https://github.com/shirou/gopsutil) provides cross-platform process monitoring. From the library documentation: "This is a port of psutil (the Python library). All works are implemented without cgo by porting C structs to golang structs." The library supports Linux (via procfs), macOS (via sysctl), and Windows (via WMI and Windows API).

The grandcat/zeroconf library (https://github.com/grandcat/zeroconf) provides cross-platform mDNS/DNS-SD support in pure Go.

### 3.2 Daemon Components

The daemon consists of these components:

**Discovery Component:** Continuously browses for `_saturn._tcp.local.` services. When a service is found, it extracts TXT records and determines if it is a beacon (has `ephemeral_key`) or an agent (has `agent=true`). Beacon credentials are cached for injection. Agent endpoints are cached for delegation.

**Advertisement Component:** Registers this machine as a Saturn service via mDNS. The TXT records indicate this is an agent and provide the URL to the Agent Card. When Claude Code connects via MCP, the daemon updates the Agent Card with the connected agent's capabilities.

**HTTP Server Component:** Serves three endpoints. The `/.well-known/agent-card.json` endpoint returns the A2A Agent Card. The `/a2a/tasks` endpoint accepts A2A Task objects for delegation. The `/v1/credentials` endpoint returns cached beacon credentials.

**MCP Server Component:** Implements the MCP protocol over stdio. Provides the four tools documented in Section 2.3.2. This is how Claude Code interacts with Saturn.

### 3.3 Component Interaction

The components interact as follows:

When the daemon starts, it begins mDNS discovery immediately. As beacons are discovered, their credentials are cached. As other Saturn agents are discovered, their Agent Card URLs are fetched and cached.

Simultaneously, the daemon registers itself via mDNS advertisement. Initially, the Agent Card contains no skills because no Claude Code instance is connected.

When Claude Code starts and connects to the Saturn MCP server, the daemon detects this connection. It updates the Agent Card to reflect that Claude Code is available, adding appropriate skills based on Claude Code's capabilities.

When Claude Code calls the `discover_agents` tool, the MCP server queries the discovery component for cached agents. It returns the list of agents with their skills.

When Claude Code calls the `delegate_task` tool, the MCP server looks up the target agent in the cache, constructs an A2A Task object, and POSTs it to the target's `/a2a/tasks` endpoint. The remote Saturn daemon receives the task, spawns Claude Code with the task as input, and returns the result.

When Claude Code calls the `get_credentials` tool, the MCP server queries the beacon cache and returns the best available credential.

---

## 4. Component Specifications

This section provides detailed specifications for each component. Implementation must conform to these specifications exactly.

### 4.1 mDNS Discovery Specification

**Service Type:** `_saturn._tcp`
**Domain:** `local.`
**Browse Interval:** 5 seconds
**Browse Timeout:** 3 seconds per browse operation

The discovery component maintains an in-memory cache of discovered services. Each cache entry contains: service name, hostname, port, priority (from TXT record), and a map of all TXT record properties.

When a service is discovered, the component checks if it is new or if its TXT records have changed. For beacon services (identified by `features=ephemeral_auth` in TXT records), the `ephemeral_key` value may change on each rotation interval. The component must detect these changes and update the beacon cache.

For agent services (identified by `agent=true` in TXT records), the component fetches the Agent Card from the URL specified in the `agent_card` TXT record. This HTTP GET request should have a timeout of 2 seconds. The Agent Card is parsed and cached.

The cache must handle service removal. When a service is no longer discovered (not seen in two consecutive browse cycles), it should be marked as stale. After three consecutive absences, it should be removed from the cache.

**Go Library:** `github.com/grandcat/zeroconf`

Example discovery code structure:

```go
resolver, err := zeroconf.NewResolver(nil)
if err != nil {
    return err
}

entries := make(chan *zeroconf.ServiceEntry)
ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
defer cancel()

go func() {
    for entry := range entries {
        // Parse TXT records into map
        props := parseTXTRecords(entry.Text)

        // Determine service type
        if props["features"] == "ephemeral_auth" {
            // This is a beacon - cache credentials
            beaconCache.Update(entry.Instance, props["ephemeral_key"], props["api"])
        } else if props["agent"] == "true" {
            // This is an agent - fetch and cache Agent Card
            cardURL := props["agent_card"]
            fetchAndCacheAgentCard(entry.Instance, cardURL)
        }
    }
}()

err = resolver.Browse(ctx, "_saturn._tcp", "local.", entries)
```

### 4.2 mDNS Advertisement Specification

**Service Name Format:** `{hostname}-agent`
**Service Type:** `_saturn._tcp`
**Domain:** `local.`
**Port:** 7827

The advertisement component registers the local machine as a Saturn agent service. The TXT records must include:

```
version=2.0                  # Saturn protocol version
agent=true                   # Indicates this is an agent service
agent_card=http://{ip}:7827/.well-known/agent-card.json
protocols=a2a,mcp            # Supported communication protocols
saturn=2.0                   # Backward compatibility field
```

The advertisement must be updated when the Agent Card changes. Since mDNS TXT records are immutable once registered (as documented in `beacons/beacon_explained.md` lines 299-304: "mDNS TXT records are immutable once registered. The zeroconf library doesn't support in-place updates. The only way to change values is to unregister and register again."), the component must unregister and re-register when changes occur.

The component must obtain the local machine's non-loopback IP address for the `agent_card` URL. On machines with multiple network interfaces, prefer the first non-loopback IPv4 address.

**Go Library:** `github.com/grandcat/zeroconf`

Example advertisement code structure:

```go
hostname, _ := os.Hostname()
localIP := getLocalIPv4()

txt := []string{
    "version=2.0",
    "agent=true",
    fmt.Sprintf("agent_card=http://%s:7827/.well-known/agent-card.json", localIP),
    "protocols=a2a,mcp",
    "saturn=2.0",
}

server, err := zeroconf.Register(
    hostname+"-agent",      // Instance name
    "_saturn._tcp",         // Service type
    "local.",               // Domain
    7827,                   // Port
    txt,                    // TXT records
    nil,                    // Interfaces (nil = all)
)
```

### 4.3 HTTP Server Specification

**Port:** 7827
**Endpoints:**

#### Endpoint: GET /.well-known/agent-card.json

Returns the A2A Agent Card for this machine. The response must conform to the A2A specification exactly.

Response Content-Type: `application/json`
Response Status: 200 OK

Example response:

```json
{
  "name": "desktop-agent",
  "description": "Saturn Agent Daemon on desktop",
  "version": "1.0.0",
  "url": "http://192.168.1.100:7827",
  "supportedInterfaces": [
    {
      "protocol": "a2a/1.0",
      "url": "http://192.168.1.100:7827/a2a"
    },
    {
      "protocol": "http",
      "url": "http://192.168.1.100:7827"
    }
  ],
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "claude-code",
      "name": "Claude Code",
      "description": "AI coding assistant with full codebase access"
    }
  ],
  "authentication": {
    "schemes": ["none"]
  }
}
```

The skills array is populated dynamically when Claude Code connects via MCP.

#### Endpoint: POST /a2a/tasks

Accepts an A2A Task object and executes it by spawning Claude Code.

Request Content-Type: `application/json`
Request Body: A2A Task object

```json
{
  "id": "task-123",
  "message": {
    "role": "user",
    "content": "Research the implementation patterns for WebSocket servers in Go"
  },
  "context": "This is for the Saturn daemon project"
}
```

Response Content-Type: `application/json`
Response Status: 200 OK (success) or 202 Accepted (async processing)

The daemon executes the task by spawning a new Claude Code process with the task content as input. The exact mechanism for spawning Claude Code and capturing its output is implementation-specific, but one approach is:

```go
cmd := exec.Command("claude", "--print", taskContent)
output, err := cmd.Output()
```

The `--print` flag (if supported) causes Claude Code to output its response and exit, rather than starting an interactive session.

#### Endpoint: GET /v1/credentials

Returns the best available API credentials from cached beacons.

Response Content-Type: `application/json`
Response Status: 200 OK (credentials available) or 404 Not Found (no beacons)

Example response:

```json
{
  "OPENAI_API_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "OPENAI_BASE_URL": "https://api.deepinfra.com/v1/openai",
  "provider": "DeepInfra",
  "expires_in": 285
}
```

The response format uses `OPENAI_API_KEY` and `OPENAI_BASE_URL` because these are the environment variable names that most AI tools expect.

### 4.4 MCP Server Specification

**Transport:** stdio (JSON-RPC 2.0 over standard input/output)
**Server Name:** saturn

The MCP server implements the JSON-RPC 2.0 protocol. It must handle these MCP methods:

**initialize:** Called when Claude Code connects. Returns server capabilities.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "Claude Code",
      "version": "1.0.0"
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "saturn",
      "version": "1.0.0"
    }
  }
}
```

**tools/list:** Returns the list of available tools.

**tools/call:** Executes a tool and returns the result.

The four tools (discover_agents, delegate_task, get_credentials, get_agent_status) are documented in Section 2.3.2.

The MCP server runs as a subprocess of the main daemon. When the daemon starts with `saturnd mcp` arguments, it runs in MCP server mode, communicating via stdio. When run without arguments, it runs as the full daemon with HTTP server and mDNS components.

Claude Code's configuration specifies the MCP server command:

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

### 4.5 Beacon Cache Specification

The beacon cache stores credentials discovered from Saturn beacons on the network. Each cache entry contains:

```go
type CachedCredential struct {
    APIKey      string    // The ephemeral_key from TXT record
    BaseURL     string    // Derived from provider (e.g., DeepInfra -> api.deepinfra.com)
    Provider    string    // The api field from TXT record
    Priority    int       // The priority field from TXT record
    DiscoveredAt time.Time // When this credential was discovered
    LastSeen    time.Time // Last time this beacon was seen
}
```

The cache must support these operations:

**Update(name string, cred CachedCredential):** Add or update a credential. Called when a beacon is discovered or when its ephemeral_key changes due to rotation.

**GetBest() (CachedCredential, bool):** Return the credential with the lowest priority value. If multiple credentials have the same priority, prefer the most recently seen.

**GetByProvider(provider string) (CachedCredential, bool):** Return a credential from a specific provider.

**Cleanup(maxAge time.Duration):** Remove credentials not seen within maxAge.

The cache must be thread-safe because discovery runs in a background goroutine while the MCP server and HTTP server access the cache from their own goroutines.

---

## 5. Implementation Details

This section provides implementation guidance for specific technical challenges.

### 5.1 Cross-Platform Local IP Detection

The daemon needs to determine the local machine's IP address for the Agent Card URL. This is non-trivial on machines with multiple network interfaces.

```go
func getLocalIPv4() string {
    addrs, err := net.InterfaceAddrs()
    if err != nil {
        return "127.0.0.1"
    }

    for _, addr := range addrs {
        if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
            if ipnet.IP.To4() != nil {
                return ipnet.IP.String()
            }
        }
    }

    return "127.0.0.1"
}
```

This returns the first non-loopback IPv4 address. On machines with multiple interfaces (e.g., Ethernet and WiFi), this may not return the "correct" interface. For Saturn's purposes, any routable local address is acceptable because mDNS operates on the local network.

### 5.2 Process Monitoring (Optional)

Process monitoring was discussed as a detection mechanism but is not required for the primary implementation. The MCP registration approach provides reliable agent detection without polling processes.

However, process monitoring can be useful for the `get_agent_status` tool to report which AI agents are running on this machine (even if they are not connected via MCP).

The gopsutil library provides cross-platform process enumeration:

```go
import "github.com/shirou/gopsutil/v3/process"

func detectAIAgents() []string {
    knownPatterns := []string{"claude", "aider", "cursor", "code", "codex", "amp"}

    procs, _ := process.Processes()
    var detected []string

    for _, p := range procs {
        name, err := p.Name()
        if err != nil {
            continue
        }

        nameLower := strings.ToLower(name)
        for _, pattern := range knownPatterns {
            if strings.Contains(nameLower, pattern) {
                detected = append(detected, name)
                break
            }
        }
    }

    return detected
}
```

From the gopsutil documentation: "On Linux, the process information is gathered by parsing text files in the procfs. Windows implementation requires direct calls to the Windows API. The macOS implementation leverages system calls like SysctlKinfoProc."

### 5.3 Graceful Shutdown

The daemon must handle shutdown signals properly to unregister from mDNS. If the daemon exits without unregistering, the service may remain in network caches for several minutes, causing clients to attempt connections to a dead service.

```go
sigChan := make(chan os.Signal, 1)
signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

// In main goroutine
<-sigChan
log.Println("Shutting down...")
advertiser.Shutdown()  // Unregisters from mDNS
httpServer.Shutdown(ctx)
os.Exit(0)
```

### 5.4 Claude Code Spawning for Task Execution

When the daemon receives an A2A task, it must spawn Claude Code to execute it. The exact command depends on Claude Code's CLI interface, which may evolve. The current approach:

```go
func executeTask(task A2ATask) (string, error) {
    // Write task content to a temporary file
    tmpFile, err := os.CreateTemp("", "saturn-task-*.md")
    if err != nil {
        return "", err
    }
    defer os.Remove(tmpFile.Name())

    tmpFile.WriteString(task.Message.Content)
    tmpFile.Close()

    // Execute Claude Code with the task
    cmd := exec.Command("claude", "--print", "-f", tmpFile.Name())
    output, err := cmd.CombinedOutput()
    if err != nil {
        return "", fmt.Errorf("claude execution failed: %w\nOutput: %s", err, output)
    }

    return string(output), nil
}
```

The `--print` flag and `-f` flag are hypothetical. The actual Claude Code CLI interface should be verified at implementation time.

### 5.5 JSON-RPC 2.0 for MCP

The MCP protocol uses JSON-RPC 2.0. Each message is a single line of JSON followed by a newline. The daemon reads lines from stdin, parses them as JSON-RPC requests, processes them, and writes JSON-RPC responses to stdout.

```go
scanner := bufio.NewScanner(os.Stdin)
encoder := json.NewEncoder(os.Stdout)

for scanner.Scan() {
    line := scanner.Text()

    var request JSONRPCRequest
    if err := json.Unmarshal([]byte(line), &request); err != nil {
        sendError(encoder, nil, -32700, "Parse error")
        continue
    }

    response := handleRequest(request)
    encoder.Encode(response)
}
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

Each component should have unit tests covering:

**Discovery Component:**
- Parsing TXT records correctly
- Detecting new vs. updated services
- Handling malformed TXT records gracefully
- Cache expiration logic

**Advertisement Component:**
- Generating correct TXT records
- Updating Agent Card when capabilities change
- Re-registration on changes

**Beacon Cache:**
- Thread-safe access from multiple goroutines
- Priority-based selection
- Expiration and cleanup

**MCP Server:**
- Parsing JSON-RPC requests
- Handling each tool correctly
- Error responses for invalid requests

### 6.2 Integration Tests

Integration tests require multiple machines or virtual machines on the same network. Test scenarios:

**Scenario 1: Basic Discovery**
Start daemon on machine A. Start daemon on machine B. Verify that A discovers B and B discovers A within 10 seconds.

**Scenario 2: Credential Injection**
Start beacon on machine A. Start daemon on machine B. Verify that B's get_credentials returns A's ephemeral key.

**Scenario 3: Task Delegation**
Start daemon on machine A with Claude Code. Start daemon on machine B with Claude Code. Have A delegate a task to B. Verify B receives and executes the task. Verify A receives the result.

### 6.3 Manual Testing

A test script should be provided that exercises all functionality:

```bash
#!/bin/bash
# test_saturn.sh

echo "Starting Saturn daemon..."
saturnd &
DAEMON_PID=$!
sleep 2

echo "Checking Agent Card..."
curl -s http://localhost:7827/.well-known/agent-card.json | jq .

echo "Checking credentials endpoint..."
curl -s http://localhost:7827/v1/credentials | jq .

echo "Stopping daemon..."
kill $DAEMON_PID
```

---

## 7. Future Work: ANS Integration

The Agent Name Service (ANS) is an OWASP initiative that provides a global registry for AI agents, inspired by DNS. The IETF Internet-Draft is available at https://datatracker.ietf.org/doc/draft-narajala-ans/.

From the ANS specification: "ANS is a novel architecture based on DNS, providing a protocol-agnostic registry mechanism that leverages PKI certificates for verifiable agent identity and trust."

ANS complements Saturn. Saturn provides local network discovery (like mDNS). ANS provides global discovery (like DNS). The architectural relationship is:

```
Local Network          Internet
     │                    │
  Saturn              ANS Registry
  (mDNS)              (DNS-like)
     │                    │
     └────────────────────┘
              │
         Federation
```

Future work includes:

**ANS Naming:** Adopt ANS naming conventions for agent identification. The ANS naming format is `Protocol://AgentID.Capability.Provider.Version`. For example: `a2a://desktop-claude.CodeReview.joeys-home.v1`

**PKI Integration:** For enterprise deployments, integrate with PKI for agent identity verification. The ANS specification requires X.509 certificates issued by a Certificate Authority.

**Registry Federation:** Connect Saturn's local discovery to global ANS registries. When an agent is not found locally, query the global registry.

This work is explicitly deferred. The current implementation focuses on local network discovery and A2A integration. ANS integration will be addressed in a future phase after the core functionality is proven.

---

## Appendix A: Sources

This section lists all sources referenced in this document.

**RFC Documents:**
- RFC 6763 "DNS-Based Service Discovery": https://www.rfc-editor.org/rfc/rfc6763.html
- RFC 8615 "Well-Known Uniform Resource Identifiers (URIs)": https://www.rfc-editor.org/rfc/rfc8615.html

**Protocol Specifications:**
- A2A Protocol Specification: https://a2a-protocol.org/latest/specification/
- A2A GitHub Repository: https://github.com/a2aproject/A2A
- MCP Specification: https://modelcontextprotocol.io/specification/2025-11-25
- MCP Anniversary Blog Post: https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/
- ANS IETF Draft: https://datatracker.ietf.org/doc/draft-narajala-ans/

**Libraries:**
- grandcat/zeroconf (Go mDNS library): https://github.com/grandcat/zeroconf
- shirou/gopsutil (Go process monitoring): https://github.com/shirou/gopsutil
- IANA Well-Known URIs Registry: https://www.iana.org/assignments/well-known-uris

**Saturn Project Documents:**
- Saturn Rings Integration: `research/rings/SATURN_RINGS_INTEGRATION.md`
- Beacon Explained: `beacons/beacon_explained.md`
- Discovery Implementation: `saturn/discovery.py`

**Wikipedia:**
- Zero-configuration networking: https://en.wikipedia.org/wiki/Zero-configuration_networking
- Daemon (computing): https://en.wikipedia.org/wiki/Daemon_(computing)
- Model Context Protocol: https://en.wikipedia.org/wiki/Model_Context_Protocol

---

## Appendix B: Glossary

**A2A (Agent-to-Agent Protocol):** An open protocol by Google enabling communication between AI agents.

**Agent Card:** A JSON document describing an agent's identity, capabilities, and communication methods. Hosted at `/.well-known/agent-card.json`.

**ANS (Agent Name Service):** An OWASP initiative for global agent discovery, similar to DNS.

**Beacon:** A Saturn service that advertises API credentials via mDNS TXT records without serving HTTP traffic.

**DNS-SD (DNS Service Discovery):** A protocol for discovering services on a network using DNS records.

**mDNS (Multicast DNS):** A protocol for resolving hostnames on local networks without a central DNS server.

**MCP (Model Context Protocol):** Anthropic's protocol for integrating LLMs with external tools and data sources.

**TXT Record:** A DNS record type containing arbitrary text, used by DNS-SD for service metadata.

---

*End of Implementation Plan*
