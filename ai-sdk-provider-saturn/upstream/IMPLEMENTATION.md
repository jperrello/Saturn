# Saturn SDK Implementation Summary

This document describes the implementation of the AI SDK provider for Saturn.

## What Was Built

### 1. Saturn Provider (`src/index.ts`)

A complete AI SDK V2 provider that:
- **Discovers services** via mDNS using the `multicast-dns` package
- **Maintains live registry** of Saturn services with background updates
- **Fetches models on-demand** from each discovered endpoint via HTTP
- **Routes requests** to appropriate services with priority-based failover
- **Handles ephemeral keys** that rotate periodically
- **Implements AI SDK V2** `LanguageModelV2` and `ProviderV2` interfaces

**Key Classes:**
- `SaturnDiscovery` - Background mDNS service discovery
- `SaturnChatLanguageModel` - Language model implementation with failover
- `createSaturn()` - Provider factory function
- `saturn` - Default provider instance

### 2. Mock Server (`src/mock-server.ts`)

An Eliza chatbot server that:
- **Announces itself via mDNS** as `_saturn._tcp.local`
- **Rotates API keys** every 60 seconds (configurable)
- **Implements classic ELIZA** pattern matching (60+ patterns)
- **Speaks OpenAI API** format for compatibility
- **Serves HTTP endpoints** for health, models, and chat completions

**Key Features:**
- Base64-encoded UUID ephemeral keys (~48 bytes)
- mDNS TXT records with priority, capabilities, cost metadata
- Bearer token authentication with key validation
- Full ELIZA response generation with pattern matching

## Design Decisions

### mDNS Discovery Strategy

**Chosen**: Pure JavaScript with `multicast-dns` package
**Alternative considered**: Shell out to `dns-sd`/`avahi-browse` commands

**Rationale**: Pure JS solution is cleaner, easier to integrate, and works consistently across platforms without system dependencies.

### Model Discovery

**Chosen**: On-demand HTTP fetch with caching
**Alternative considered**: Announce models in TXT records

**Rationale**: TXT records have ~250 byte size limits. With ephemeral keys taking ~150 bytes, there's insufficient space for model lists. HTTP fetching provides implicit "sticky" behavior - services are only queried when first needed.

### Failover Strategy

**Chosen**: Priority-based with per-model failover
**Implementation**:
1. Discover all services advertising the requested model
2. Sort by priority (lower = preferred)
3. Try each service in order until success
4. Aggregate models from all services

This allows running multiple Saturn servers (e.g., local Ollama + cloud OpenRouter) with automatic fallback.

### Key Format

**Chosen**: Base64-encoded UUID
**Size**: ~48 bytes
**Alternative considered**: JWT tokens

**Rationale**: JWTs are ~150+ bytes and would exceed TXT record size limits. Base64 UUIDs provide sufficient uniqueness and fit comfortably within constraints.

### Streaming Implementation

**Chosen**: Server-Sent Events (SSE) parsing
**Implementation**: Transform stream that converts OpenAI SSE chunks to AI SDK V2 stream parts

**Details**:
- Handles `text-delta`, `tool-input-start/delta/end` events
- Tracks active text/tool streams with IDs
- Properly closes streams on finish

## Technical Challenges Solved

### 1. AI SDK Version Mismatch

**Problem**: Documentation referenced V3 API, but published package uses V2
**Solution**: Checked actual type definitions and implemented against V2

**V2 Differences**:
- `FinishReason` is a string, not an object with `unified` and `raw`
- `Usage` requires `totalTokens` field
- `ToolCall` content has `input: string`, not `args: unknown`
- Stream parts use `delta` not `textDelta`

### 2. mDNS Hostname Resolution

**Problem**: SRV records return hostnames like `hostname.local`, not IPs
**Solution**: Listen for A/AAAA records and resolve hostnames to IPs, updating services when resolved

### 3. Service Lifecycle Management

**Problem**: Services can appear/disappear dynamically
**Solution**:
- Track `lastSeen` timestamp for each service
- Periodic cleanup removes stale services (60s timeout)
- Update existing services when TXT records change (key rotation)

### 4. ESM Module Compatibility

**Problem**: Used `require('os')` in ESM module
**Solution**: Import `hostname` from `node:os` directly

### 5. CLI Shebang Duplication

**Problem**: Source file had shebang, tsup was adding another
**Solution**: Remove tsup banner config, rely on source file shebang

## File Structure

```
saturn-sdk/
├── src/
│   ├── index.ts          # Main provider (20KB compiled)
│   └── mock-server.ts    # Eliza server (18KB compiled)
├── dist/                 # Build output (ESM + .d.ts)
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript config
├── tsup.config.ts        # Build config
├── README.md             # User documentation
└── .gitignore
```

## Dependencies

### Runtime
- `@ai-sdk/provider` - AI SDK types and interfaces
- `@ai-sdk/provider-utils` - Helper utilities (generateId, etc.)
- `multicast-dns` - Pure JS mDNS implementation

### Development
- `typescript` - Type checking
- `tsup` - Bundler (esbuild-based)
- `tsx` - TypeScript executor for dev

**Bundle Size**: ~20KB for provider, ~18KB for mock server

## Usage Pattern

```typescript
import { saturn } from 'ai-sdk-provider-saturn';
import { generateText } from 'ai';

// Discovery runs in background automatically
const result = await generateText({
  model: saturn('eliza'),  // Discovers services with 'eliza' model
  prompt: 'Hello',
});
```

**Discovery Flow**:
1. Provider starts → `SaturnDiscovery.start()`
2. Send mDNS query for `_saturn._tcp.local`
3. Receive PTR → query SRV+TXT
4. Parse host, port, priority, ephemeral_key from records
5. Resolve hostname to IP if needed
6. First model request → fetch `/v1/models` from all services
7. Cache models list per service
8. Route request to best available service

## Testing

Start mock server:
```bash
npm run mock
```

The server:
- Listens on random available port
- Announces via mDNS
- Rotates key every 60 seconds
- Responds to chat requests with ELIZA patterns

Test endpoints:
```bash
# Health check
curl http://localhost:PORT/v1/health

# Models list
curl http://localhost:PORT/v1/models

# Chat (requires auth header with current ephemeral key)
curl -H "Authorization: Bearer KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"eliza","messages":[{"role":"user","content":"Hello"}]}' \
     http://localhost:PORT/v1/chat/completions
```

## Future Enhancements

1. **Embedding Support**: Implement `EmbeddingModelV2` for text embeddings
2. **Image Generation**: Implement `ImageModelV2` for image models
3. **Model Caching TTL**: Refresh models list periodically
4. **Connection Pooling**: Reuse HTTP connections across requests
5. **Metrics**: Track request counts, latencies, failover events
6. **Service Health**: Periodic health checks beyond discovery
7. **Streaming Retry**: Retry mid-stream on connection loss

## References

- [AI SDK Documentation](https://ai-sdk.dev/)
- [Saturn Protocol](https://jperrello.github.io/Saturn/)
- [multicast-dns Package](https://github.com/mafintosh/multicast-dns)
- [DNS-SD (RFC 6763)](https://datatracker.ietf.org/doc/html/rfc6763)
