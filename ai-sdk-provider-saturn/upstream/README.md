# AI SDK Provider for Saturn

Zero-configuration AI service discovery for the [AI SDK](https://ai-sdk.dev/). This provider automatically discovers Saturn services on your local network via mDNS/DNS-SD and routes requests to them with priority-based failover.

## Features

- **Zero Configuration**: Services are discovered automatically via mDNS - no manual endpoint configuration needed
- **Background Discovery**: Continuous service discovery with automatic updates when services appear/disappear
- **Priority-Based Failover**: Automatically tries the next available service if one fails
- **Ephemeral Key Rotation**: Supports Saturn's rotating API key system
- **Model Aggregation**: Discovers models from all available services
- **Mock Server Included**: Eliza chatbot server for testing

## Installation

```bash
npm install ai-sdk-provider-saturn
```

## Quick Start

### Using the Provider

```typescript
import { saturn } from 'ai-sdk-provider-saturn';
import { generateText } from 'ai';

// Discovery starts automatically in the background
const result = await generateText({
  model: saturn('eliza'),
  prompt: 'I am feeling anxious about my work',
});

console.log(result.text);
// "How long have you been feeling anxious about your work?"
```

### Running the Mock Server

Start the included Eliza chatbot server for testing:

```bash
# Via npm script
npm run mock

# Or if installed globally
npx saturn-mock-server

# With options
npx saturn-mock-server --port 8080 --priority 10 --name "MyEliza"
```

The mock server:
- Announces itself via mDNS as `_saturn._tcp.local`
- Rotates its API key every 60 seconds (configurable)
- Implements classic ELIZA pattern matching
- Speaks OpenAI-compatible HTTP API

## Usage Examples

See the `examples/` directory for complete working examples:

- **`simple-query.ts`** - Basic non-streaming query
- **`streaming-chat.ts`** - Streaming response example
- **`chat-with-eliza.ts`** - Interactive chat loop
- **`discovery-info.ts`** - Service discovery details

### Running Examples

```bash
# Start the mock server in one terminal
npm run mock

# In another terminal, run an example
npm run example:simple     # Simple query
npm run example:stream     # Streaming chat
npm run example:chat       # Interactive chat
npm run example:discovery  # Discovery info
```

### Basic Usage

```typescript
import { saturn } from 'ai-sdk-provider-saturn';
import { generateText } from 'ai';

// Wait a moment for service discovery
await new Promise(resolve => setTimeout(resolve, 3000));

const result = await generateText({
  model: saturn('eliza'),
  prompt: 'I am feeling anxious',
});

console.log(result.text);
// "How long have you been feeling anxious?"
```

### Streaming

```typescript
import { saturn } from 'ai-sdk-provider-saturn';
import { streamText } from 'ai';

// Wait for discovery
await new Promise(resolve => setTimeout(resolve, 3000));

const { textStream } = await streamText({
  model: saturn('eliza'),
  prompt: 'I need help',
});

for await (const chunk of textStream) {
  process.stdout.write(chunk);
}
```

### Custom Provider Settings

```typescript
import { createSaturn } from 'ai-sdk-provider-saturn';

const mySaturn = createSaturn({
  discoveryTimeout: 5000, // Wait up to 5s for initial discovery
});

const model = mySaturn('eliza');
```

### Advanced: Direct Discovery Access

```typescript
import { createSaturn } from 'ai-sdk-provider-saturn';

const provider = createSaturn();
const discovery = provider.getDiscovery();

// Get all discovered services
const services = discovery.getAllServices();
console.log('Found services:', services.map(s => s.name));

// Cleanup when done
provider.destroy();
```

## How It Works

### Service Discovery Flow

1. **mDNS Query**: Provider sends multicast DNS query for `_saturn._tcp.local` services
2. **Service Resolution**: Resolves SRV and TXT records to get host, port, and metadata
3. **Model Fetching**: Calls `GET /v1/models` on each discovered endpoint
4. **Request Routing**: Routes AI SDK requests to appropriate service based on model availability and priority

### Failover Strategy

When you request a model (e.g., `saturn('eliza')`):

1. Provider finds all services advertising that model
2. Sorts services by priority (lower numbers = higher priority)
3. Attempts request to highest priority service
4. On connection failure, automatically retries with next service
5. Throws error only if all services fail

### Key Rotation

Saturn services can rotate their ephemeral API keys:

- Keys are announced in mDNS TXT records (`ephemeral_key` field)
- Provider automatically updates cached keys when TXT records change
- Mock server rotates keys every 60 seconds by default

## Mock Server Details

### Eliza Response Engine

The mock server implements classic ELIZA pattern matching:

```
User: "I am feeling sad"
Eliza: "How long have you been feeling sad?"

User: "I need help with my work"
Eliza: "Why do you need help with your work?"
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Health check (no auth) |
| `/v1/models` | GET | List available models |
| `/v1/chat/completions` | POST | Chat completions (requires auth) |

### mDNS Announcement

The mock server announces itself with these TXT record fields:

```
txtvers=1
saturn=2.0
priority=50
transport=http
auth=psk
cost=free
capabilities=chat
ephemeral_key=<base64-uuid>
```

### Command-Line Options

```bash
saturn-mock-server [options]

Options:
  --port, -p       Port to listen on (default: random available)
  --priority       Service priority (default: 50)
  --name, -n       Service name (default: "Eliza")
  --rotation, -r   Key rotation interval in seconds (default: 60)
  --help, -h       Show help
```

## Development

```bash
# Install dependencies
npm install

# Type check
npm run typecheck

# Build
npm run build

# Run mock server (dev mode)
npm run mock
```

## Architecture

### Discovery (`SaturnDiscovery`)

- Background mDNS listener using `multicast-dns` package
- Maintains live registry of discovered services
- Tracks ephemeral key rotation
- On-demand model fetching with caching

### Language Model (`SaturnChatLanguageModel`)

- Implements AI SDK `LanguageModelV2` interface
- Converts AI SDK prompt format to OpenAI messages
- Priority-based failover across services
- Streaming and non-streaming support

### Provider (`SaturnProvider`)

- Implements AI SDK `ProviderV2` interface
- Factory for creating language models
- Manages discovery lifecycle

## Protocol Details

### mDNS Service Type

```
_saturn._tcp.local
```

### TXT Record Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `txtvers` | Yes | TXT record version | `"1"` |
| `saturn` | Yes | Saturn protocol version | `"2.0"` |
| `priority` | Yes | Service priority (lower = preferred) | `"50"` |
| `transport` | Yes | Protocol for API | `"http"` |
| `ephemeral_key` | No | Base64-encoded rotating key | `"YTM4NDU2..."` |
| `auth` | No | Authentication type | `"psk"`, `"bearer"`, `"none"` |
| `capabilities` | No | Service capabilities | `"chat,code,vision"` |
| `cost` | No | Pricing tier | `"free"`, `"paid"`, `"unknown"` |

### HTTP API

Saturn services expose OpenAI-compatible HTTP endpoints:

- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions (streaming/non-streaming)
- `GET /v1/health` - Health check

## Related Projects

- [Saturn](https://github.com/jperrello/Saturn) - Zero-configuration AI service discovery
- [AI SDK](https://ai-sdk.dev/) - Vercel AI SDK for TypeScript

## License

MIT
