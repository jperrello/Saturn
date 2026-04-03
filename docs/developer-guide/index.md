# Developer Guide

Saturn lets you drop AI into any application without requiring users to configure anything. No auth logic, no config UI, no billing integration. Call `discover()`, get services with URLs and credentials already populated, make HTTP requests.

The integration pattern is the same regardless of language or platform:

1. Discover services on the local network via mDNS/DNS-SD
2. Select the best service by priority
3. Make standard HTTP requests to OpenAI-compatible endpoints

Six reference implementations across Python, Rust, TypeScript, and Lua prove the protocol works cross-platform. Every implementation follows the same discovery protocol and talks to the same endpoints.

## Pages

- [Protocol Specification](protocol.md) -- DNS-SD record structure, TXT record schema, endpoint requirements
- [Discovery Flow](discovery.md) -- the 4-step browse/resolve/select/connect sequence with code examples
- [Beacons](beacons.md) -- ephemeral key rotation, local vs cloud beacons, key lifecycle
- [Security Model](security.md) -- threat models, broadcast exposure, trust boundaries
- [Python Package](python-package.md) -- `saturn-ai` package API reference
- [AI SDK Provider](ai-sdk-provider.md) -- `ai-sdk-provider-saturn` for TypeScript with Vercel AI SDK
- [Router](router.md) -- `saturn-router` Rust implementation for OpenWRT
- [REST API](api.md) -- all endpoints exposed by `saturn web`
- [MCP Tools](mcp-tools.md) -- Model Context Protocol tools and resources
