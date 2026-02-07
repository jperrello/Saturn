# Saturn AI SDK Provider — Implementation Specification (Revised)

>
> **Purpose**: Complete specification for finishing the Saturn AI SDK provider implementation.
>
> **Source Code**: Adam's draft is in `./upstream/` (cloned from https://github.com/rndmcnlly/ai-sdk-provider-saturn)
>

---

## Table of Contents

1. [Background: What is Saturn?](#1-background-what-is-saturn)
2. [Background: What is AI SDK?](#2-background-what-is-ai-sdk)
3. [The Goal](#3-the-goal)
4. [Architecture Overview](#4-architecture-overview)
5. [TXT Record Schema (Production)](#5-txt-record-schema-production)
6. [Current Implementation Analysis](#6-current-implementation-analysis)
7. [Gap Analysis](#7-gap-analysis)
8. [Required Changes](#8-required-changes)
9. [Logging & Observability](#9-logging--observability)
10. [Error Recovery Patterns](#10-error-recovery-patterns)
11. [Testing Strategy](#11-testing-strategy)
12. [CI/CD Pipeline](#12-cicd-pipeline)
13. [Documentation Requirements](#13-documentation-requirements)
14. [Publishing Roadmap](#14-publishing-roadmap)
15. [Reference Links](#15-reference-links)

---

## 1. Background: What is Saturn?

Saturn is a **zero-configuration service discovery system** for AI services. It uses mDNS (Multicast DNS) and DNS-SD (DNS Service Discovery) to automatically advertise and locate OpenAI-compatible AI backends on a local network.

**The problem it solves**: Instead of every application needing its own API key and configuration for AI services, Saturn makes AI access a network-level resource. Like connecting to a printer via Bonjour—users don't configure IP addresses, they just print.

### Saturn Service Types

Saturn has **two deployment modes** (from `saturn-router`):

#### Cloud Deployments (Beacons)
- Advertise credentials for a **remote** API (OpenRouter, OpenAI, DeepInfra)
- May use ephemeral key rotation for security
- Clients discover the key and call the upstream provider directly via `api_base`
- Example: Router advertises rotating OpenRouter API keys

#### Network Deployments (Proxies)
- Advertise the location of a **local** LAN service (Ollama, vLLM)
- Clients connect to the host:port on the local network
- Example: Router advertises local Ollama instance at 192.168.1.100:11434

**This distinction is critical** — Adam's current implementation doesn't parse the `deployment` field.

---

## 2. Background: What is AI SDK?

AI SDK (https://ai-sdk.dev/) is Vercel's TypeScript framework for building AI applications. It provides a unified interface for interacting with different LLM providers.

### Why This Matters

Many applications are built on AI SDK:
- **OpenCode** (AI-powered code editor)
- Various Vercel AI templates
- Thousands of community projects

If Saturn has an AI SDK provider, all these applications can use Saturn with minimal code changes.

### AI SDK Provider Architecture

From https://ai-sdk.dev/providers/community-providers/custom-providers:

1. **ProviderV2/V3 Interface**: Factory that creates models
2. **LanguageModelV2/V3 Interface**: The actual model implementation with:
   - `specificationVersion: 'v2'` or `'V3'`
   - `supportedUrls`: Which URLs the provider can access natively
   - `doGenerate()`: Non-streaming generation
   - `doStream()`: Streaming generation

### Reference Implementation

The docs recommend using **Mistral** as the gold standard:
- Repository: https://github.com/vercel/ai/tree/main/packages/mistral
- Key patterns:
  - Private `getArgs()` method shared by doGenerate/doStream
  - Warnings for unsupported features (don't throw, just warn)
  - `supportedUrls` declaration (even if empty)

---

## 3. The Goal

**Immediate Goal**: Fix Adam's draft so it correctly handles both Saturn cloud AND network deployments.

**Medium-term Goal**: Upgrade to LanguageModelV3 spec for future-proofing.

**Long-term Goal**: Get Saturn included in:
1. AI SDK community providers documentation
2. OpenCode's `BUNDLED_PROVIDERS` list

### Success Criteria

1. `saturn('model-name')` works with a Saturn **cloud** deployment (beacon)
2. `saturn('model-name')` works with a Saturn **network** deployment (proxy)
3. Clear error message when no Saturn services are discovered
4. Deployment metadata exposed to applications (can filter cloud vs network)
5. Structured logging for debugging discovery issues
6. Integration tests passing against real OpenRouter
7. Published to npm

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Application                        │
│                   (e.g., OpenCode, custom app)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ import { saturn } from 'ai-sdk-provider-saturn'
                                │ saturn('gpt-4')
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SaturnProvider (AI SDK)                      │
│  - Starts mDNS discovery                                        │
│  - Creates SaturnChatLanguageModel instances                    │
│  - Exposes deployment metadata to applications                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ discovery.getEndpointsForModel('gpt-4')
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SaturnDiscovery                             │
│  - Listens for _saturn._tcp.local mDNS announcements            │
│  - Parses TXT records (deployment, api_type, api_base, etc.)    │
│  - Maintains live registry of services                          │
│  - Logs discovery events for debugging                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │  NETWORK Deployment│  │   CLOUD Deployment │
        │   (Local Proxy)    │   │     (Beacon)       │
        │                   │   │                   │
        │ deployment=network │   │ deployment=cloud   │
        │ api_type=ollama    │   │ api_type=openai    │
        │ host: 192.168.1.5 │   │ api_base: https:// │
        │ port: 11434        │   │   openrouter.ai/   │
        │                   │   │   api/v1           │
        │ Call:             │   │ ephemeral_key:    │
        │ http://192.168.   │   │   sk-abc123...    │
        │ 1.5:11434/v1/...  │   │                   │
        └───────────────────┘   │ Call:             │
                                │ https://openrou..│
                                │ /v1/... with key  │
                                └───────────────────┘
```

---

## 5. TXT Record Schema (Production)

**IMPORTANT**: The production implementation is `saturn-router` (Rust), not the Python beacons. This schema reflects the Rust implementation from `saturn-router/src/providers/provider.rs`.

### TXT Record Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `version` | string | `"1.0"` | Schema version |
| `deployment` | enum | `"cloud"` \| `"network"` | **Required**. Deployment type |
| `api_type` | enum | `"openai"` \| `"ollama"` | **Required**. API compatibility |
| `api_base` | string | URL | Base URL for API calls |
| `priority` | int | 0-100 | Lower = preferred |
| `ephemeral_key` | string | API key | Only for cloud + ephemeral mode |
| `rotation_interval` | int | seconds | Key rotation interval |
| `features` | string | `"ephemeral_auth"` \| `"network_proxy"` | Feature flags |

### Cloud Deployment Example (OpenRouter Beacon)

```
version           = "1.0"
deployment        = "cloud"
api_type          = "openai"
api_base          = "https://openrouter.ai/api/v1"
priority          = "10"
ephemeral_key     = "sk-or-v1-abc123..."
rotation_interval = "300"
features          = "ephemeral_auth"
```

### Network Deployment Example (Local Ollama)

```
version           = "1.0"
deployment        = "network"
api_type          = "ollama"
api_base          = "http://192.168.1.100:11434"
priority          = "50"
features          = "network_proxy"
```

### Key Insight: Routing Logic

```typescript
function getEffectiveEndpoint(service: DiscoveredService): string {
  if (service.deployment === 'cloud') {
    return service.apiBase;  // Call upstream provider directly
  }
  return `http://${service.host}:${service.port}/v1`;  // Call local proxy
}
```

---

## 5.1 Python Implementation Status (COMPLETED)

> **Status**: ✅ The Python Saturn servers and clients have been updated to match the production TXT record schema.
>
> **Date**: January 2025
>
> **Changes Made**:

The following Python files were updated to align with the Rust `saturn-router` TXT record schema:

### Server-Side Changes

| File | Changes |
|------|---------|
| `saturn/discovery.py` | Updated `SaturnService` dataclass with production fields (`version`, `deployment`, `api_type`, `api_base`, `features`, `rotation_interval`). Updated `SaturnAdvertiser` to emit production-compatible TXT records. Added `is_cloud`, `is_network`, `effective_endpoint` properties. |
| `saturn/openrouter_beacon.py` | Changed `api` → `api_type='openai'`, added `deployment='cloud'` |
| `saturn/deepinfra_beacon.py` | Changed `api` → `api_type='openai'`, added `deployment='cloud'` |
| `saturn/openrouter_server.py` | Updated `SaturnAdvertiser` call with `deployment='network'`, `api_type='openai'` |
| `saturn/ollama_server.py` | Updated `SaturnAdvertiser` call with `deployment='network'`, `api_type='ollama'` |
| `saturn/beacon_proxy.py` | Updated `SaturnAdvertiser` call with new parameters |
| `saturn/fallback_server.py` | Updated `SaturnAdvertiser` call with new parameters |
| `saturn/aider_saturn.py` | Updated to use `is_cloud` property and new field names |
| `saturn/README.md` | Updated documentation with production schema |

### Client-Side Changes

| File | Changes |
|------|---------|
| `clients/simple_chat_client.py` | Added `deployment`, `api_type`, `features` fields. Added `is_cloud` and `effective_endpoint` properties. Updated TXT record parsing. |

### What This Means for AI SDK Provider Development

The Python servers now emit TXT records that match the schema expected by Section 5:

```
version=1.0
deployment=cloud|network
api_type=openai|ollama
api_base=<URL>
priority=<number>
ephemeral_key=<key>        (cloud only)
rotation_interval=<seconds> (cloud only)
features=ephemeral_auth|network_proxy
```

**The AI SDK provider (`upstream/src/index.ts`) still needs to be updated** to parse these fields — see Sections 6-8 below.

---

## 6. Current Implementation Analysis

Adam's implementation is in `./upstream/src/index.ts`. Let me break down each component:

### 6.1 SaturnDiscovery Class (lines 113-315)

**What it does well:**
- Uses `multicast-dns` npm package for mDNS (line 21)
- Queries for `_saturn._tcp.local` PTR records (line 105)
- Handles SRV records for host/port (lines 188-201)
- Handles TXT records for metadata (lines 203-228)
- Tracks ephemeral key rotation (lines 220-226)
- Fetches `/v1/models` on-demand (lines 275-299)

**What's missing:**
- Does NOT parse `deployment` from TXT records
- Does NOT parse `api_type` from TXT records
- Does NOT parse `api_base` from TXT records
- No structured logging

### 6.2 parseTxtRecords Method (lines 231-251)

Current implementation only parses:
- `priority`
- `ephemeral_key`
- `auth`
- `capabilities`
- `cost`

**Missing cases:**
- `deployment` — required for routing
- `api_type` — required for endpoint construction
- `api_base` — required for cloud deployments
- `features` — useful for metadata

### 6.3 fetchModelsForService Method (lines 275-299)

**Problem**: Always uses `service.endpoint` which is `http://{host}:{port}/v1`. For cloud deployments, should use `api_base` instead.

### 6.4 SaturnChatLanguageModel Class (lines 339-591)

**What's wrong:**
- Uses `LanguageModelV2` not `LanguageModelV3` (line 341)
- `specificationVersion = 'v2'` should be `'V3'` (line 341)
- `callEndpoint` always uses `service.endpoint` (line 445) — wrong for cloud deployments

### 6.5 DiscoveredService Interface (lines 26-51)

**Missing fields:**
- `deployment: 'cloud' | 'network'`
- `apiType: 'openai' | 'ollama'`
- `apiBase: string`
- `provider: string` (derived from apiBase)

---

## 7. Gap Analysis

| Component | Current State | Required State | Priority |
|-----------|--------------|----------------|----------|
| `DiscoveredService.deployment` | Missing | Add required field | **P0** |
| `DiscoveredService.apiType` | Missing | Add required field | **P0** |
| `DiscoveredService.apiBase` | Missing | Add required field | **P0** |
| `parseTxtRecords()` | Missing production fields | Parse deployment, api_type, api_base | **P0** |
| `fetchModelsForService()` | Uses `endpoint` | Use routing logic | **P0** |
| `callEndpoint()` | Uses `endpoint` | Use routing logic | **P0** |
| Structured logging | None | Add discovery/routing logs | **P1** |
| Error recovery | Basic try/catch | Retry, circuit breaker | **P1** |
| `specificationVersion` | `'v3'` ✅ | `'v3'` | DONE |
| Integration tests | None | Real OpenRouter tests | **P1** |
| CI/CD | None | GitHub Actions | P2 |

---

## 8. Required Changes

### 8.1 Update DiscoveredService Interface

**File**: `upstream/src/index.ts`
**Lines**: 26-51

```typescript
export interface DiscoveredService {
  name: string;
  host: string;
  port: number;
  endpoint: string;  // Computed: http://{host}:{port}/v1
  priority: number;
  ephemeralKey: string;
  authType: 'none' | 'psk' | 'bearer';
  capabilities: string[];
  cost: 'free' | 'paid' | 'unknown';
  models: string[];
  modelsLastFetched: number | null;

  // NEW FIELDS (from saturn-router TXT schema)
  deployment: 'cloud' | 'network';
  apiType: 'openai' | 'ollama';
  apiBase: string;
  features: string;

  // DERIVED FIELDS (computed client-side)
  provider: string;  // Extracted from apiBase
}

// Helper functions
export function isCloudDeployment(service: DiscoveredService): boolean {
  return service.deployment === 'cloud';
}

export function getEffectiveEndpoint(service: DiscoveredService): string {
  if (service.deployment === 'cloud') {
    return service.apiBase;
  }
  return service.endpoint;
}

export function extractProvider(apiBase: string): string {
  try {
    const url = new URL(apiBase);
    const host = url.hostname.toLowerCase();
    if (host.includes('openrouter')) return 'OpenRouter';
    if (host.includes('openai')) return 'OpenAI';
    if (host.includes('deepinfra')) return 'DeepInfra';
    if (host.includes('anthropic')) return 'Anthropic';
    return host;
  } catch {
    return 'Unknown';
  }
}
```

### 8.2 Update PartialService Interface

**File**: `upstream/src/index.ts`
**Lines**: 54-65

```typescript
interface PartialService {
  name: string;
  host?: string;
  port?: number;
  priority?: number;
  ephemeralKey?: string;
  authType?: 'none' | 'psk' | 'bearer';
  capabilities?: string[];
  cost?: 'free' | 'paid' | 'unknown';
  lastSeen: number;

  // NEW
  deployment?: 'cloud' | 'network';
  apiType?: 'openai' | 'ollama';
  apiBase?: string;
  features?: string;
}
```

### 8.3 Update parseTxtRecords Method

**File**: `upstream/src/index.ts`
**Lines**: 231-251

Add cases:
```typescript
case 'deployment':
  if (value === 'cloud' || value === 'network') {
    partial.deployment = value;
  }
  break;
case 'api_type':
  if (value === 'openai' || value === 'ollama') {
    partial.apiType = value;
  }
  break;
case 'api_base':
  partial.apiBase = value;
  break;
case 'features':
  partial.features = value;
  break;
```

### 8.4 Update tryPromoteService Method

**File**: `upstream/src/index.ts`
**Lines**: 254-273

```typescript
const service: DiscoveredService = {
  name: partial.name,
  host: partial.host,
  port: partial.port,
  endpoint: `http://${partial.host}:${partial.port}/v1`,
  priority: partial.priority ?? 50,
  ephemeralKey: partial.ephemeralKey ?? '',
  authType: partial.authType ?? 'none',
  capabilities: partial.capabilities ?? [],
  cost: partial.cost ?? 'unknown',
  models: [],
  modelsLastFetched: null,

  // NEW
  deployment: partial.deployment ?? 'network',  // Default to network
  apiType: partial.apiType ?? 'openai',
  apiBase: partial.apiBase ?? `http://${partial.host}:${partial.port}/v1`,
  features: partial.features ?? '',
  provider: extractProvider(partial.apiBase ?? ''),
};
```

### 8.5 Update fetchModelsForService Method

**File**: `upstream/src/index.ts`
**Lines**: 275-299

```typescript
private async fetchModelsForService(service: DiscoveredService): Promise<void> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Use ephemeral key if available
    if (service.ephemeralKey) {
      headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
    }

    // Use the correct endpoint based on deployment type
    const baseUrl = getEffectiveEndpoint(service);

    this.log('debug', `Fetching models from ${service.name}`, { baseUrl, deployment: service.deployment });

    const response = await fetch(`${baseUrl}/models`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      this.log('warn', `Models fetch failed for ${service.name}`, { status: response.status });
      return;
    }

    const data = (await response.json()) as OpenAIModelsResponse;
    service.models = data.data.map((m) => m.id);
    service.modelsLastFetched = Date.now();

    this.log('info', `Discovered ${service.models.length} models on ${service.name}`);
  } catch (error) {
    this.log('error', `Error fetching models from ${service.name}`, { error });
  }
}
```

### 8.6 Update callEndpoint Method

**File**: `upstream/src/index.ts`
**Lines**: 433-450

```typescript
private async callEndpoint(
  service: DiscoveredService,
  body: Record<string, unknown>,
  abortSignal?: AbortSignal
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Use ephemeral key if available
  if (service.ephemeralKey) {
    headers['Authorization'] = `Bearer ${service.ephemeralKey}`;
  }

  // Use the correct endpoint based on deployment type
  const baseUrl = getEffectiveEndpoint(service);
  const url = `${baseUrl}/chat/completions`;

  this.log('debug', `Calling ${service.name}`, {
    url,
    deployment: service.deployment,
    provider: service.provider
  });

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: abortSignal,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    this.log('warn', `Request failed for ${service.name}`, { status: response.status, error: errorBody });
    throw new Error(`HTTP ${response.status}: ${errorBody}`);
  }

  return response;
}
```

### 8.7 Update doStream's Inline Fetch

**File**: `upstream/src/index.ts`
**Lines**: 519-535

Same pattern — use `getEffectiveEndpoint(service)` instead of `service.endpoint`.

### 8.8 Improve No-Service Error Message

**File**: `upstream/src/index.ts`
**Lines**: 459-465

```typescript
if (endpoints.length === 0) {
  const allServices = this.discovery.getAllServices();

  if (allServices.length === 0) {
    throw new Error(
      `No Saturn services discovered on network. ` +
      `Ensure a Saturn router/beacon is running and advertising via mDNS (_saturn._tcp.local). ` +
      `If running saturn-router, check 'logread | grep saturn' on the router.`
    );
  }

  const serviceList = allServices.map(s =>
    `${s.name} (${s.deployment}/${s.apiType}, models: ${s.models.join(', ') || 'none fetched'})`
  ).join('; ');

  throw new NoSuchModelError({
    modelId: this.modelId,
    modelType: 'languageModel',
    message: `Model '${this.modelId}' not found on any discovered Saturn service. ` +
      `Found ${allServices.length} service(s): ${serviceList}`,
  });
}
```

---

## 9. Logging & Observability

### 9.1 Logging Interface

Add a configurable logging interface:

```typescript
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface SaturnLogger {
  log(level: LogLevel, message: string, data?: Record<string, unknown>): void;
}

// Default console logger
const defaultLogger: SaturnLogger = {
  log(level, message, data) {
    const prefix = `[Saturn/${level.toUpperCase()}]`;
    if (data) {
      console[level === 'debug' ? 'log' : level](`${prefix} ${message}`, data);
    } else {
      console[level === 'debug' ? 'log' : level](`${prefix} ${message}`);
    }
  }
};
```

### 9.2 Log Events

Log these events at appropriate levels:

| Event | Level | Data |
|-------|-------|------|
| Service discovered | info | name, deployment, apiType, priority |
| Service removed (stale) | info | name |
| Models fetched | info | name, modelCount |
| Models fetch failed | warn | name, status, error |
| Request routed | debug | serviceName, url, deployment |
| Request failed | warn | serviceName, status, error |
| Failover triggered | info | fromService, toService, reason |
| Ephemeral key rotated | info | serviceName |
| Discovery started | info | timeout |
| Discovery stopped | info | serviceCount |

### 9.3 Provider Settings

```typescript
export interface SaturnProviderSettings {
  discoveryTimeout?: number;
  logger?: SaturnLogger;
  logLevel?: LogLevel;  // Filter logs below this level
}
```

---

## 10. Error Recovery Patterns

### 10.1 Retry with Exponential Backoff

```typescript
async function withRetry<T>(
  fn: () => Promise<T>,
  options: { maxAttempts: number; baseDelay: number; maxDelay: number }
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt < options.maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < options.maxAttempts - 1) {
        const delay = Math.min(
          options.baseDelay * Math.pow(2, attempt),
          options.maxDelay
        );
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }

  throw lastError;
}
```

### 10.2 Circuit Breaker

Track service failures and temporarily skip failing services:

```typescript
interface CircuitState {
  failures: number;
  lastFailure: number;
  state: 'closed' | 'open' | 'half-open';
}

class ServiceCircuitBreaker {
  private circuits = new Map<string, CircuitState>();
  private readonly threshold = 3;        // Failures before open
  private readonly resetTimeout = 30000; // 30s before half-open

  recordFailure(serviceName: string): void { /* ... */ }
  recordSuccess(serviceName: string): void { /* ... */ }
  isAvailable(serviceName: string): boolean { /* ... */ }
}
```

### 10.3 Graceful Key Expiration Handling

If an ephemeral key is rejected (401), wait for the next key rotation instead of failing:

```typescript
if (response.status === 401 && service.ephemeralKey) {
  this.log('warn', `Ephemeral key expired for ${service.name}, waiting for rotation`);
  // Mark service as temporarily unavailable
  // Continue to next service in priority order
}
```

---

## 11. Testing Strategy

### 11.1 Test Location

Tests live inside `ai-sdk-provider-saturn/` using standard npm test setup.

**Recommended test runner**: Vitest (fast, TypeScript-native, good mocking)

### 11.2 Test Types

#### Unit Tests (mocked mDNS)

```typescript
describe('parseTxtRecords', () => {
  it('parses cloud deployment TXT records', () => {
    const partial: PartialService = { name: 'test', lastSeen: Date.now() };
    const txtData = [
      Buffer.from('deployment=cloud'),
      Buffer.from('api_type=openai'),
      Buffer.from('api_base=https://openrouter.ai/api/v1'),
      Buffer.from('ephemeral_key=sk-test'),
    ];

    discovery['parseTxtRecords'](partial, txtData);

    expect(partial.deployment).toBe('cloud');
    expect(partial.apiType).toBe('openai');
    expect(partial.apiBase).toBe('https://openrouter.ai/api/v1');
    expect(partial.ephemeralKey).toBe('sk-test');
  });

  it('parses network deployment TXT records', () => { /* ... */ });
});

describe('getEffectiveEndpoint', () => {
  it('returns apiBase for cloud deployments', () => { /* ... */ });
  it('returns local endpoint for network deployments', () => { /* ... */ });
});

describe('extractProvider', () => {
  it('identifies OpenRouter', () => { /* ... */ });
  it('identifies OpenAI', () => { /* ... */ });
  it('returns hostname for unknown providers', () => { /* ... */ });
});
```

#### Integration Tests (Real OpenRouter)

**Prerequisites:**
- `OPENROUTER_API_KEY` environment variable
- Running Saturn service (saturn-router or Python beacon)

```typescript
describe('Saturn Provider Integration', () => {
  let saturn: SaturnProvider;

  beforeAll(async () => {
    // Start saturn-router or wait for existing service
    saturn = createSaturn({ discoveryTimeout: 10000 });
    await new Promise(r => setTimeout(r, 10000)); // Wait for discovery
  });

  afterAll(() => {
    saturn.destroy();
  });

  it('discovers Saturn services on the network', () => {
    const services = saturn.getDiscovery().getAllServices();
    expect(services.length).toBeGreaterThan(0);
  });

  it('completes a chat request via cloud deployment', async () => {
    const result = await generateText({
      model: saturn('openai/gpt-3.5-turbo'),
      prompt: 'Say "hello"',
      maxTokens: 10,
    });

    expect(result.text).toBeTruthy();
  });

  it('streams a chat response via cloud deployment', async () => {
    const chunks: string[] = [];

    const { textStream } = await streamText({
      model: saturn('openai/gpt-3.5-turbo'),
      prompt: 'Count to 3',
      maxTokens: 20,
    });

    for await (const chunk of textStream) {
      chunks.push(chunk);
    }

    expect(chunks.length).toBeGreaterThan(0);
  });
});
```

### 11.3 Test Scripts

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:integration": "INTEGRATION=true vitest run --config vitest.integration.config.ts"
  }
}
```

---

## 12. CI/CD Pipeline

### 12.1 GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Type check
        run: npm run type-check

      - name: Lint
        run: npm run lint

      - name: Unit tests
        run: npm test

  # Integration tests run separately (require secrets)
  integration:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: build
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Integration tests
        run: npm run test:integration
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

### 12.2 Release Workflow

**File**: `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Publish to npm
        run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

---

## 13. Documentation Requirements

### 13.1 README.md Structure

1. **Quick Start** — 5-line example
2. **What is Saturn?** — Brief explanation
3. **Installation** — npm install command
4. **Usage Examples**
   - Basic usage
   - With streaming
   - Filtering by deployment type
   - Custom logger
5. **Configuration Options** — Table of settings
6. **Troubleshooting**
   - "No services discovered"
   - "Model not found"
   - "Connection refused"
7. **Development** — Contributing guide

### 13.2 API Documentation

Document all exported types and functions:
- `createSaturn(options?)`
- `SaturnProvider`
- `SaturnDiscovery`
- `DiscoveredService`
- `isCloudDeployment(service)`
- `getEffectiveEndpoint(service)`

### 13.3 Integration Examples

Provide examples for:
- OpenCode integration
- Next.js API route
- Express server
- CLI tool

---

## 14. Publishing Roadmap

### Phase 0: Python Server Alignment (COMPLETED ✅)
- [x] Update Python servers to emit production TXT record schema
- [x] Update Python beacons (`openrouter_beacon.py`, `deepinfra_beacon.py`) with `deployment=cloud`, `api_type=openai`
- [x] Update Python clients to parse new TXT record fields
- [x] Update `saturn/README.md` with production schema documentation

### Phase 1: Make It Work (P0) — TypeScript SDK
- [ ] Implement TXT record parsing in `upstream/src/index.ts` (deployment, api_type, api_base)
- [ ] Implement routing logic (getEffectiveEndpoint)
- [ ] Add basic logging
- [ ] Test with real Python Saturn servers (now emitting correct schema)

### Phase 2: Make It Robust (P1)
- [ ] Add error recovery (retry, circuit breaker)
- [ ] Add comprehensive logging
- [ ] Write unit tests
- [ ] Write integration tests with OpenRouter

### Phase 3: Make It Correct (P2)
- [x] Upgrade to LanguageModelV3 ✅ (completed)
- [x] Add warnings for unsupported features ✅ (completed)
- [x] Follow Mistral patterns (getArgs, etc.) ✅ (completed)

### Phase 4: Publish (P2)
- [ ] Clean up package.json (proper exports, types)
- [ ] Write comprehensive README
- [ ] Set up CI/CD
- [ ] Publish to npm as `ai-sdk-provider-saturn`

### Phase 5: Ecosystem Integration (P3)
- [ ] Submit PR to AI SDK docs
- [ ] Submit PR to OpenCode's BUNDLED_PROVIDERS
- [ ] Create announcement / blog post

---

## 15. Reference Links

### Saturn Codebase
- **Rust Router**: `saturn-router/` — Production beacon implementation
- **TXT Records**: `saturn-router/src/providers/provider.rs` lines 269-293
- **Python Beacon (legacy)**: `saturn/openrouter_beacon.py`
- **Python Client Example**: `clients/simple_chat_client.py`

### AI SDK Documentation
- Providers overview: https://ai-sdk.dev/docs/foundations/providers-and-models
- Custom providers guide: https://ai-sdk.dev/providers/community-providers/custom-providers
- LanguageModelV3 spec: https://github.com/vercel/ai/tree/main/packages/provider/src/language-model/v3
- Mistral reference: https://github.com/vercel/ai/tree/main/packages/mistral

### Adam's Implementation
- Repository: https://github.com/rndmcnlly/ai-sdk-provider-saturn
- Main source: `./upstream/src/index.ts`
- Mock server: `./upstream/src/mock-server.ts`

### OpenCode (Target Integration)
- BUNDLED_PROVIDERS: https://github.com/anomalyco/opencode/blob/main/packages/opencode/src/provider/provider.ts#L56

---

## Appendix: Quick Reference

### Deployment Detection Logic
```typescript
function isCloudDeployment(service: DiscoveredService): boolean {
  return service.deployment === 'cloud';
}
```

### Endpoint Routing Logic
```typescript
function getEffectiveEndpoint(service: DiscoveredService): string {
  return service.deployment === 'cloud'
    ? service.apiBase
    : service.endpoint;
}
```

### TXT Records to Parse
| Field | Required | Cloud | Network | Description |
|-------|----------|-------|---------|-------------|
| `deployment` | ✓ | `cloud` | `network` | Deployment type |
| `api_type` | ✓ | `openai` | varies | API compatibility |
| `api_base` | ✓ | URL | URL | Base URL for API |
| `priority` | ✓ | number | number | Lower = preferred |
| `ephemeral_key` | ✗ | key | — | API key (cloud only) |
| `rotation_interval` | ✗ | seconds | — | Key rotation (cloud only) |
| `features` | ✗ | `ephemeral_auth` | `network_proxy` | Feature flags |
