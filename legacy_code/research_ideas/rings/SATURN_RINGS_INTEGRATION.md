# Saturn Rings: Zero-Configuration AI Service Discovery for the MCP Ecosystem

**Authors:** Joey Perrello (human), Claude (AI)
**Date:** January 3, 2026
**Status:** Implementation Plan

---

## Executive Summary

Saturn is a zero-configuration AI service discovery system that uses mDNS and DNS-SD to automatically locate AI backend services on local networks. This document proposes extending Saturn to become the **local discovery layer for the Model Context Protocol (MCP)** ecosystem.

The core insight: **Saturn is to AI inference what Bonjour was to printing.**

Just as Bonjour eliminated "which printer do I use?" by letting printers announce themselves, Saturn eliminates "which AI service do I use?" by letting AI backends announce themselves. The result: developers join a network and AI just works.

This document introduces **`_rings._tcp`**—a new DNS-SD service type for MCP-compatible AI services discovered via Saturn. The name evokes Saturn's rings: all the AI services circling around you, available for use.

---

## Part 1: Background

### What is Saturn?

Saturn is Joey Perrello's master's project at UC Santa Cruz, developed under advisors Adam and Ram. It addresses a fundamental problem in AI tooling: **the API key configuration burden**.

Most AI-powered tools require users to:
1. Sign up for API access (OpenAI, Anthropic, etc.)
2. Generate API keys
3. Configure keys in each tool they use
4. Manage billing separately per tool
5. Repeat this for every machine they work on

This creates an N×M problem: N developers × M tools = N×M configurations. Saturn inverts this model:

**Before:** Every client configures how to reach every provider
**After:** Providers advertise themselves; clients discover what's available

A household, university, or office sets up Saturn servers once, and everyone on that network gets AI access. Open source developers can add AI features to their applications without burdening users with API costs.

### How Saturn Works Today

Saturn uses mDNS (Multicast DNS) and DNS-SD (DNS Service Discovery).

**Server Registration:**
1. Server finds an available port (tries 8080+, incrementing until free)
2. Runs DNS-SD browse to check existing priorities, auto-resolves conflicts by incrementing
3. Registers via `dns-sd -R` or Python zeroconf library
4. Maintains persistent mDNS announcement with TXT records (priority, version, api type, features)

**Client Discovery:**
1. Background thread runs continuous discovery loop
2. Browses for `_saturn._tcp.local` services
3. For each service, looks up hostname, port, and TXT records
4. Resolves hostname to IP, sorts by priority, connects to best available

**Priority-Based Routing:**
Lower numbers = higher priority. Clients automatically select the lowest-priority healthy service. Health monitoring polls `/v1/health` every 20 seconds, enabling automatic failover.

**Server Types:**
- **OpenRouter Server**: Proxies to OpenRouter API, supports streaming via SSE
- **Ollama Server**: Connects to local Ollama, translates between Ollama's JSON-per-line format and OpenAI's SSE format
- **Fallback Server**: Mock server for testing and failover demonstrations

All servers expose identical OpenAI-compatible endpoints: `/v1/health`, `/v1/models`, `/v1/chat/completions`.

### What is mDNS/DNS-SD?

**mDNS (Multicast DNS)** allows devices to resolve hostnames without a central DNS server. When your laptop looks for `adams-workstation.local`, it sends a multicast query on the local network, and Adam's workstation responds directly.

**DNS-SD (DNS Service Discovery)** builds on mDNS to advertise services. A printer announces itself as `Joey's Printer._ipp._tcp.local` with TXT records describing its capabilities. Your laptop discovers it without any configuration.

Key components:
- **Service Instance Name**: `adams-ollama._saturn._tcp.local` (human-readable name + service type + domain)
- **Service Type**: `_saturn._tcp` (protocol identifier, max 15 characters)
- **TXT Records**: Key-value metadata (priority=10, version=1.0, models=llama3)
- **SRV Record**: Host and port where service is reachable

This technology is 20+ years battle-tested. AirPlay, Chromecast, HomeKit, and Matter all use it.

### What is MCP?

The **Model Context Protocol (MCP)** is an open standard introduced by Anthropic in November 2024 that standardizes how AI systems integrate with external tools and data sources.

**Key Dates:**
- November 2024: Anthropic introduces MCP
- March 2025: OpenAI adopts MCP across products including ChatGPT desktop
- September 2025: MCP Registry launches, now cataloging ~2,000 servers
- November 2025: Major spec update with async operations, server identity, streamable-http transport
- December 2025: Anthropic donates MCP to the Agentic AI Foundation under Linux Foundation

**MCP's Architecture:**
- **Clients**: AI applications (Claude, ChatGPT, Cursor, VS Code)
- **Servers**: Tools and data sources (databases, APIs, file systems)
- **Transport**: Originally stdio, now primarily streamable-http
- **Registry**: Central index at mcp.so for discovering public MCP servers

**The Gap MCP Has:**
MCP has excellent support for public/cloud server discovery via the Registry. But it has no standard mechanism for **local network discovery**. If you run an MCP server on your LAN (Ollama, private database connector, internal API gateway), other machines must be manually configured to find it.

This is exactly the gap Saturn fills.

---

## Part 2: The Conversation—How We Got Here

This document emerged from a structured conversation between Joey Perrello and Claude on January 3, 2026. The dialogue shaped the technical direction through iterative refinement.

### Joey's Initial Vision

Joey arrived with research documents exploring how Saturn could impact the emerging "Gas Town" ecosystem—Steve Yegge's multi-agent coding orchestrator. The design fictions showed:

1. **Steve's Gas Town Empire**: Joey visits Steve's house. His laptop discovers Steve's mature Gas Town setup. Without any configuration, Joey uses Steve's workers and inference to solve a frontend problem, taking home a portable record of the work.

2. **Adam's GPU Bailout**: Joey is burning $100/hour on cloud inference. He visits Adam, who has an RTX 5090 running Ollama. The moment Joey connects to WiFi, his Gas Town discovers the local inference and routes there—saving hundreds with zero configuration.

### Claude's Analysis

Claude read the research documents, the Fall 2025 Saturn Report, and Steve Yegge's "Gas Town" article. The analysis identified:

**What Inspires:**
- The invisibility principle: success is measured by how little users think about Saturn
- The AirPlay architectural parallel: mDNS for discovery, separate protocol for interaction
- The cost arbitrage opportunity: hybrid local/cloud routing creates economic value from idle hardware
- The MCP timing: MCP becoming standard, but lacking local discovery

**What Seemed Infeasible:**
1. Multi-person Gas Town federation at scale
2. Transparent inference routing across latency boundaries
3. Security without friction
4. Adoption dependency chain

### Joey's Corrections

Joey pushed back on several points:

**On Naming:** Claude proposed `_mcp-model._tcp.local`. Joey: "I don't understand why you would go with that name. We should stay on theme—something Saturn-related that gives off the idea of what we're trying to achieve. I chose Saturn because it has rings, and rings are figuratively all the AI services on your network."

The chosen name: **`_rings._tcp`**

**On Security:** Joey: "Security is not a big issue for me because if you're on the local network then you've already trusted the admin. This is a master's project and I will be getting a security advisor soon. For now, perhaps a naive password authenticator."

**On Risk:** Joey: "We need to jump on this bandwagon now. Everything is theoretical and has limitations, but AI is moving so quickly that if I want to get ahead, we need to take those risks."

**On Zero-Configuration:** Joey: "Remember—one developer, zero configuration. Saturn makes setting up and gaining AI access as simple as possible. This is the ultimate goal."

### The Technical Interview

Claude administered a technical interview to verify Joey understood his own infrastructure:

- **Priority conflicts**: Joey correctly identified that servers auto-increment on startup to resolve conflicts
- **Format translation**: Joey correctly identified that Ollama uses JSON-per-line while OpenAI uses SSE `data:` prefix
- **DNS-SD structure**: Joey correctly identified that instance name is unique ID, type is category, TXT is metadata
- **Health monitoring**: Joey correctly identified `/v1/health` every 20 seconds

Joey passed 4/4, demonstrating solid understanding of the technical foundation.

---

## Part 3: Solutions to Feasibility Concerns

Claude initially identified four areas as "not feasibly possible." Here are concrete solutions:

### 1. Multi-Person Federation at Scale

**The Concern:** Federation creates billing complexity, version compatibility issues, and conflict resolution problems. This works peer-to-peer between friends but breaks at organizational scale.

**The Solution: Start Small, Design for Growth**

- **Phase 1 (Now)**: Peer-to-peer between 2-3 trusted friends. No formal billing—gift economy. Explicit version negotiation in TXT records.
- **Phase 2 (Later)**: Metered tracking. Saturn logs usage per federated peer. Settlement happens out-of-band (Venmo, expense reports).
- **Phase 3 (Future)**: Organizational federation with proper IAM integration.

Conflict resolution: namespace prefixes. `steve/refactor-safe` and `joey/refactor-safe` are distinct. The originating installation is part of the identity.

This isn't solving federation at scale—it's scoping federation to what's achievable now and designing extension points for later.

### 2. Transparent Inference Routing Across Latency Boundaries

**The Concern:** Routing from cloud (100ms) to local Ollama (10ms) mid-conversation creates capability and context discontinuity.

**The Solution: Sticky Sessions, Explicit Boundaries**

- **Don't route mid-conversation.** Once a task starts with a provider, it stays with that provider.
- **Route at task boundary.** When Gas Town starts a new polecat/worker, it evaluates available inference and picks the best option for that task.
- **Make routing visible.** The Gas Town Mayor shows which inference each worker is using. This isn't invisible magic—it's informed automation.

Quality-threshold routing (`quality-threshold = 0.80`) applies to **new tasks**, not ongoing ones. Sticky sessions provide consistency; routing provides optimization.

### 3. Security Without Friction

**The Concern:** Real organizations have compliance requirements, audit trails, and data exfiltration concerns. Adding security adds friction, breaking the Bonjour analogy.

**The Solution: Layers of Trust, Not One-Size-Fits-All**

- **Layer 0 (Default)**: Network membership = trust. If you're on the WiFi, admin already trusted you. No additional auth. This is the Bonjour model.
- **Layer 1 (Simple)**: Pre-shared key (PSK). Saturn servers can require a password advertised via TXT record hash. Simple, but effective for home/lab use.
- **Layer 2 (Enterprise)**: Integrate with existing network auth. 802.1X, VPN certificates, OAuth tokens. Saturn doesn't reinvent auth—it delegates to whatever the network already uses.

For Joey's master's project, Layer 0 or Layer 1 is sufficient. The architecture supports Layer 2 when needed.

### 4. Adoption Dependency Chain

**The Concern:** The full vision requires Saturn → coding agent integration → Gas Town integration → MCP spec adoption. Each step depends on the previous. The chain is fragile.

**The Solution: Demonstrate Value at Each Step**

- **Step 1**: Saturn works standalone. It already does. Clients can discover and use inference without any coding agent integration.
- **Step 2**: Show Saturn + one coding agent. Aider is easiest (environment variable based). A PR demonstrating Saturn discovery doesn't require Aider to accept it—the demo proves the concept.
- **Step 3**: Show Saturn + Gas Town. Since Gas Town will embed Saturn, this is within Joey's control.
- **Step 4**: Propose to MCP spec. By then, there's working code to point to.

The chain isn't "wait for X before starting Y." It's "build X, demonstrate value, build Y on top, demonstrate more value."

---

## Part 4: Technical Integration Plan

### Service Type: `_rings._tcp`

Saturn introduces a new DNS-SD service type for MCP-compatible AI services:

```
_rings._tcp.local
```

The name evokes Saturn's rings—all the AI services circling around you, available for use. This is distinct from `_saturn._tcp` (the existing general Saturn service type) and signals MCP compatibility.

### TXT Record Schema

When a Saturn server advertises an MCP-compatible service, it includes:

```
txtvers=1                    # TXT record version
saturn=2.0                   # Saturn protocol version
mcp=2025-11-25               # MCP spec version supported
transport=http               # MCP transport type (http, stdio)
models=llama3,mixtral        # Comma-separated available models
context=128000               # Maximum context window
capabilities=chat,code       # Supported capabilities
cost=free                    # Cost tier: free, local, metered
auth=none                    # Auth requirement: none, psk, token
```

Optional fields for metered/enterprise deployments:

```
psk_hash=sha256:abc123...    # Hash of pre-shared key (if auth=psk)
priority=10                  # Routing priority (lower = preferred)
version=1.2.3                # Server software version
```

### Discovery Flow

1. **Agent starts** (Gas Town, Aider, Cursor, etc.)
2. **Saturn client queries** `_rings._tcp.local` via mDNS
3. **Available servers respond** with SRV records (host:port) and TXT records (capabilities)
4. **Agent evaluates options:**
   - Filter by required capabilities (needs vision? needs code?)
   - Filter by context window requirements
   - Sort by priority, then by cost tier, then by latency
5. **Agent connects via MCP** using discovered endpoint
6. **No manual configuration required**

### Code Example: Discovery Client

```python
# saturn_rings.py
import time
from zeroconf import ServiceBrowser, Zeroconf
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RingsService:
    name: str
    host: str
    port: int
    models: List[str]
    context_window: int
    capabilities: List[str]
    cost_tier: str
    priority: int
    mcp_version: str

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def mcp_endpoint(self) -> str:
        return f"{self.endpoint}/mcp"

class RingsDiscovery:
    SERVICE_TYPE = "_rings._tcp.local."

    def __init__(self):
        self.services: List[RingsService] = []
        self._zeroconf = None
        self._browser = None

    def discover(self, timeout: float = 3.0) -> List[RingsService]:
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(
            self._zeroconf,
            self.SERVICE_TYPE,
            self
        )

        time.sleep(timeout)

        self._zeroconf.close()
        return sorted(self.services, key=lambda s: (s.priority, s.cost_tier))

    def add_service(self, zc, service_type, name):
        info = zc.get_service_info(service_type, name)
        if info:
            txt = {k.decode(): v.decode() for k, v in info.properties.items()}

            self.services.append(RingsService(
                name=name.replace(f".{service_type}", ""),
                host=info.server.rstrip('.'),
                port=info.port,
                models=txt.get("models", "").split(","),
                context_window=int(txt.get("context", 4096)),
                capabilities=txt.get("capabilities", "").split(","),
                cost_tier=txt.get("cost", "unknown"),
                priority=int(txt.get("priority", 100)),
                mcp_version=txt.get("mcp", "unknown"),
            ))

    def remove_service(self, zc, service_type, name):
        self.services = [s for s in self.services if s.name != name]

    def update_service(self, zc, service_type, name):
        self.remove_service(zc, service_type, name)
        self.add_service(zc, service_type, name)

def discover_rings(timeout: float = 3.0) -> List[RingsService]:
    return RingsDiscovery().discover(timeout)

def select_best_service(
    services: List[RingsService],
    needs: Optional[List[str]] = None,
    min_context: int = 0,
    prefer_free: bool = True
) -> Optional[RingsService]:
    candidates = services

    if needs:
        candidates = [s for s in candidates
                     if all(n in s.capabilities for n in needs)]

    if min_context:
        candidates = [s for s in candidates
                     if s.context_window >= min_context]

    if not candidates:
        return None

    if prefer_free:
        free = [s for s in candidates if s.cost_tier == "free"]
        if free:
            return free[0]

    return candidates[0]
```

### Code Example: Server Advertisement

```python
# saturn_rings_server.py
from zeroconf import ServiceInfo, Zeroconf
import socket

class RingsAdvertiser:
    def __init__(
        self,
        name: str,
        port: int,
        models: list,
        context_window: int = 128000,
        capabilities: list = None,
        cost_tier: str = "local",
        priority: int = 50,
        mcp_version: str = "2025-11-25"
    ):
        self.name = name
        self.port = port
        self.models = models
        self.context_window = context_window
        self.capabilities = capabilities or ["chat"]
        self.cost_tier = cost_tier
        self.priority = priority
        self.mcp_version = mcp_version

        self._zeroconf = None
        self._info = None

    def start(self):
        self._zeroconf = Zeroconf()

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        self._info = ServiceInfo(
            "_rings._tcp.local.",
            f"{self.name}._rings._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={
                "txtvers": "1",
                "saturn": "2.0",
                "mcp": self.mcp_version,
                "transport": "http",
                "models": ",".join(self.models),
                "context": str(self.context_window),
                "capabilities": ",".join(self.capabilities),
                "cost": self.cost_tier,
                "priority": str(self.priority),
                "auth": "none",
            },
            server=f"{hostname}.local.",
        )

        self._zeroconf.register_service(self._info)
        print(f"Advertising {self.name}._rings._tcp.local on port {self.port}")

    def stop(self):
        if self._zeroconf and self._info:
            self._zeroconf.unregister_service(self._info)
            self._zeroconf.close()
```

### Integration with Existing Saturn Servers

Existing Saturn servers (OpenRouter, Ollama, etc.) can advertise on both `_saturn._tcp` and `_rings._tcp`:

```python
# In servers/ollama_server.py, add dual registration

def register_services(self):
    # Existing Saturn registration
    self.register_saturn_service()

    # New Rings registration for MCP compatibility
    self.rings_advertiser = RingsAdvertiser(
        name=f"{socket.gethostname()}-ollama",
        port=self.port,
        models=self.get_ollama_models(),
        context_window=self.get_max_context(),
        capabilities=["chat", "code"],
        cost_tier="free",
        priority=self.priority,
    )
    self.rings_advertiser.start()
```

This maintains backward compatibility while signaling MCP readiness to new clients.

### Integration with Coding Agents

**Aider Integration (Environment Variable):**

```bash
# Without Saturn
export OPENAI_API_KEY=sk-...
aider

# With Saturn Rings
export OPENAI_BASE_URL=$(saturn-rings discover --first)
export OPENAI_API_KEY=saturn-managed
aider
```

**Programmatic Integration:**

```python
# In any coding agent's initialization
from saturn_rings import discover_rings, select_best_service

def get_inference_client():
    services = discover_rings()

    if services:
        service = select_best_service(
            services,
            needs=["code"],
            min_context=64000
        )
        if service:
            return OpenAI(
                base_url=service.endpoint,
                api_key="saturn-managed"
            )

    # Fallback to direct API
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
```

---

## Part 5: Implementation Phases

### Phase 1: Rings Discovery (Current Focus)

**Goal:** Demonstrate `_rings._tcp` discovery working with existing Saturn servers.

**Deliverables:**
- `saturn_rings.py` client library (discovery, selection)
- `saturn_rings_server.py` advertiser component
- Dual registration in Ollama and OpenRouter servers
- CLI tool: `saturn-rings discover`, `saturn-rings select`
- Unit tests for discovery and selection logic

**Success Criteria:** Run `saturn-rings discover` on any machine on Joey's network and see available AI services. Connect and make an inference request with zero configuration.

### Phase 2: Coding Agent Integration

**Goal:** Show Saturn Rings working with one real coding agent.

**Target:** Aider (simplest integration—environment variable based)

**Approach:**
1. Create `aider-saturn` wrapper script
2. Discover services, set `OPENAI_BASE_URL` and `OPENAI_API_KEY`
3. Launch Aider
4. Document the integration
5. (Optional) Submit PR to Aider repo

**Success Criteria:** Developer joins Saturn-enabled network, runs `aider-saturn`, and uses AI without configuring API keys.

### Phase 3: Gas Town Embedding

**Goal:** Gas Town discovers inference via Saturn Rings and workers via federation.

**Note:** This depends on Gas Town's architecture, which is still evolving. The plan:
1. Gas Town embeds `saturn_rings.py`
2. Mayor configuration gains `saturn` provider type
3. Workers automatically use discovered inference
4. Federation uses similar discovery pattern (`_convoy._tcp`?)

**Success Criteria:** The design fiction scenarios (Steve's Gas Town Empire, Adam's GPU Bailout) become real.

### Phase 4: MCP Specification Proposal

**Goal:** Propose `_rings._tcp` (or equivalent) as an optional transport/discovery mechanism in the MCP specification.

**Timing:** After Phase 2-3 demonstrate working implementations.

**Approach:**
1. Write RFC-style proposal document
2. Reference working implementations
3. Submit to MCP maintainers (now under Linux Foundation governance)
4. Engage with MCP community for feedback

**Success Criteria:** MCP spec acknowledges mDNS/DNS-SD as a valid discovery mechanism for local servers.

---

## Part 6: Future Directions

### Saturn Layer 2: Awareness Services

Joey's `saturn_awareness_service.py` represents a parallel track: giving agents visibility into costs, usage, and network presence. This is orthogonal to discovery but complementary.

Future integration:
- Discovery tells you **what's available**
- Awareness tells you **what it costs** and **how you've been using it**

These could be separate services or combined into a single Saturn agent MCP server.

### Federation Protocol

For multi-person Gas Town, beyond inference discovery, we need:
- Worker discovery (`_convoy._tcp`?)
- Formula registry sharing
- Session/task handoff
- Usage attribution

This is future work, but the DNS-SD foundation supports it.

### Enterprise Features

For organizational deployment:
- Integration with LDAP/Active Directory for access control
- Audit logging to SIEM systems
- Cost allocation tags for chargeback
- Rate limiting per user/department

The architecture supports this via the TXT record `auth` field and future extensions.

### Cross-Network Discovery

mDNS is local-network only. For discovery across network boundaries:
- DNS-SD over unicast DNS (works today, requires DNS infrastructure)
- Saturn registry service (like MCP Registry, but for Saturn networks)
- VPN/overlay network integration

This moves Saturn from "household/office" to "organization-wide."

---

## Conclusion

Saturn Rings (`_rings._tcp`) represents the natural evolution of Saturn from basic inference discovery to a first-class participant in the MCP ecosystem. The technical foundation is solid—mDNS/DNS-SD are battle-tested protocols. The timing is right—MCP is becoming the standard but lacks local discovery. The vision is clear—zero-configuration AI access for everyone on the network.

The path forward:
1. Implement `_rings._tcp` discovery (Phase 1)
2. Integrate with one coding agent (Phase 2)
3. Embed in Gas Town for federation (Phase 3)
4. Propose to MCP specification (Phase 4)

Each phase delivers value independently while building toward the larger vision.

**The ultimate goal remains: one developer, zero configuration.**

---

## References

- [MCP Specification (November 2025)](https://modelcontextprotocol.io/specification/2025-11-25)
- [Anthropic Donates MCP to Linux Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation)
- [RFC 6763: DNS-Based Service Discovery](https://datatracker.ietf.org/doc/html/rfc6763)
- [Apple Domain Naming Conventions](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/NetServices/Articles/domainnames.html)
- [Welcome to Gas Town - Steve Yegge](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Gas Town Discussion - Hacker News](https://news.ycombinator.com/item?id=46458936)

---

*This document was created through collaborative dialogue between Joey Perrello and Claude on January 3, 2026.*
