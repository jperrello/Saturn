# Saturn + A2A: Complete Architecture

This document is the canonical reference for the Saturn Agent Daemon implementation. All implementation work must conform to this architecture.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                  SATURN + A2A: COMPLETE ARCHITECTURE                         │
│                                                                              │
│  DESKTOP                                    LAPTOP                           │
│  ────────                                   ──────                           │
│                                                                              │
│  ┌────────────────────┐                     ┌────────────────────┐          │
│  │ Claude Code        │                     │ Claude Code        │          │
│  │                    │                     │                    │          │
│  │ MCP Client ────────┼─────────────────────┼────MCP Client      │          │
│  └────────┬───────────┘                     └───────────┬────────┘          │
│           │                                             │                    │
│           │ stdio                                       │ stdio              │
│           ▼                                             ▼                    │
│  ┌────────────────────┐                     ┌────────────────────┐          │
│  │ Saturn Daemon      │                     │ Saturn Daemon      │          │
│  │ (saturnd)          │◄────── mDNS ───────▶│ (saturnd)          │          │
│  │                    │   _saturn._tcp      │                    │          │
│  │ • MCP Server       │                     │ • MCP Server       │          │
│  │ • HTTP :7827       │                     │ • HTTP :7827       │          │
│  │ • mDNS Advertiser  │                     │ • mDNS Advertiser  │          │
│  │ • Process Monitor  │                     │ • Process Monitor  │          │
│  │ • Beacon Cache     │                     │ • Beacon Cache     │          │
│  └────────┬───────────┘                     └───────────┬────────┘          │
│           │                                             │                    │
│           │ HTTP GET                                    │ HTTP GET           │
│           ▼                                             ▼                    │
│  ┌────────────────────┐                     ┌────────────────────┐          │
│  │ /.well-known/      │                     │ /.well-known/      │          │
│  │ agent-card.json    │                     │ agent-card.json    │          │
│  │                    │                     │                    │          │
│  │ {                  │                     │ {                  │          │
│  │  "name": "desktop",│                     │  "name": "laptop", │          │
│  │  "skills": [       │                     │  "skills": [       │          │
│  │    "refactoring",  │                     │    "research",     │          │
│  │    "code_review"   │                     │    "documentation" │          │
│  │  ]                 │                     │  ]                 │          │
│  │ }                  │                     │ }                  │          │
│  └────────────────────┘                     └────────────────────┘          │
│                                                                              │
│  DELEGATION FLOW:                                                           │
│  ────────────────                                                           │
│  1. Desktop Claude needs research help                                      │
│  2. Calls MCP tool: discover_agents()                                       │
│  3. Saturn daemon returns: [{name: "laptop", skills: ["research"]}]         │
│  4. Claude calls MCP tool: delegate_task("laptop", "research X")            │
│  5. Saturn daemon POSTs A2A Task to laptop:7827/a2a/tasks                   │
│  6. Laptop Saturn daemon spawns Claude Code with task                       │
│  7. Result returned via A2A response                                        │
│  8. Desktop Claude receives result via MCP tool response                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Summary

| Component | Port | Protocol | Purpose |
|-----------|------|----------|---------|
| Saturn MCP Server | stdio | MCP (JSON-RPC 2.0) | Claude Code integration |
| Saturn HTTP Server | 7827 | HTTP | Agent Cards, A2A endpoints, credential API |
| Saturn mDNS | N/A | mDNS/DNS-SD | Service discovery on `_saturn._tcp.local.` |

## MCP Server Name

The MCP server is named `saturn` (not `saturn-mcp` or `saturn-agent`). Users configure it in their Claude Code settings as:

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

## Key Design Decisions

1. Agent detection uses MCP registration (Approach B from research), not process monitoring
2. API key injection uses MCP tools (Method B from research), not environment variables
3. Service type remains `_saturn._tcp.local.` with TXT records indicating agent capabilities
4. A2A Agent Cards follow the official A2A specification exactly
5. ANS (Agent Name Service) integration is deferred to a future phase
