# Saturn Agent Daemon (saturnd)

This directory contains the Go implementation of the Saturn Agent Daemon.

## Status: Scaffolding Only

The `.go` files in this directory are **scaffolding/examples only**. They were created during initial design exploration and are **incomplete**.

## Authoritative Documentation

Implementers must follow:

1. **Architecture**: `../research/A2A_MCP/ARCHITECTURE.md`
2. **Implementation Plan**: `../research/A2A_MCP/IMPLEMENTATION_PLAN.md`

The implementation plan contains:
- Complete specifications for each component
- Code examples with correct patterns
- Testing requirements
- Acceptance criteria

## Issues

Work is tracked in beads. Run `bd ready` to see available work:

- `Saturn-sk9`: Core Daemon + mDNS Discovery/Advertisement
- `Saturn-irk`: Beacon Credential Caching
- `Saturn-ahd`: System Service Installation Scripts
- `Saturn-ccq`: HTTP Server + A2A Agent Cards (blocked)
- `Saturn-dlj`: MCP Server for Claude Code Integration (blocked)
- `Saturn-ask`: A2A Task Delegation Endpoint (blocked)
- `Saturn-f4w`: Integration Testing and Component Review (blocked)

## Building

Once implementation is complete:

```bash
cd saturnd
go build -o saturnd ./cmd/saturnd
```

## Running

As daemon:
```bash
./saturnd
```

As MCP server (for Claude Code):
```bash
./saturnd mcp
```
