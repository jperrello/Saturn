# Developer Guide

Saturn is a wire protocol — DNS-SD on `_saturn._tcp.local.` plus OpenAI-compatible HTTP. To integrate, you implement (or borrow) the three steps below in whatever language the host application speaks. There is no Saturn-specific SDK requirement; conformance is defined by the records and the endpoints, not by shared code.

1. Browse `_saturn._tcp.local.` via mDNS/DNS-SD; resolve PTR → SRV → TXT for each instance.
2. Sort by TXT `priority` (lower wins); pick the lowest healthy.
3. Issue standard HTTP requests against the resulting `host:port` (or `api_base` for cloud deployments).

Reference implementations exist in Go (`saturnd`), Python, Rust, TypeScript, and Lua across four mDNS libraries. They share no Saturn-specific code — they share the protocol.

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
