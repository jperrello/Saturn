# AI SDK Provider

The `ai-sdk-provider-saturn` package integrates Saturn discovery into the Vercel AI SDK for TypeScript and JavaScript applications.

## Installation

```bash
npm install ai-sdk-provider-saturn
```

## Circuit Breaker

<svg class="saturn-diagram" viewBox="0 0 700 220" xmlns="http://www.w3.org/2000/svg" width="700" height="220" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="700" height="220" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-accent" x="40" y="70" width="140" height="60" rx="30" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="110" y="105" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">Closed</text>
  <text class="diagram-text" x="110" y="145" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">(requests flow)</text>
  <line class="diagram-line" x1="180" y1="90" x2="270" y2="90" stroke-width="2" marker-end="url(#arrow3)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="225" y="80" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">3 failures</text>
  <rect class="diagram-box" x="270" y="70" width="140" height="60" rx="30" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="340" y="105" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">Open</text>
  <text class="diagram-text" x="340" y="145" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">(requests blocked)</text>
  <line class="diagram-line" x1="410" y1="90" x2="500" y2="90" stroke-width="2" marker-end="url(#arrow3)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="455" y="80" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">30s cooldown</text>
  <rect class="diagram-accent" x="500" y="70" width="160" height="60" rx="30" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="580" y="105" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">Half-Open</text>
  <text class="diagram-text" x="580" y="145" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">(probe request)</text>
  <path class="diagram-line" d="M 580 70 Q 580 20 110 20 Q 40 20 40 70" fill="none" stroke-width="2" marker-end="url(#arrow3)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="350" y="15" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">success</text>
  <path class="diagram-line" d="M 500 130 Q 450 190 410 130" fill="none" stroke-width="2" marker-end="url(#arrow3)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="430" y="195" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">failure</text>
  <defs>
    <marker id="arrow3" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-line" points="0 0, 10 3.5, 0 7" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

## Features

- Implements Vercel AI SDK `ProviderV3` interface
- Uses `multicast-dns` npm library for mDNS discovery
- Circuit breaker: threshold 3 failures, reset after 30s cooldown
- Direct mode: bypass mDNS, connect to a known endpoint
- Dynamic model registration/unregistration via event callbacks
- Auto-failover between services

## Usage

```typescript
import { createSaturnProvider } from 'ai-sdk-provider-saturn'
import { generateText } from 'ai'

const saturn = createSaturnProvider({ timeout: 5000 })

const { text } = await generateText({
  model: saturn('service/model'),
  prompt: 'Hello'
})
```

The provider discovers Saturn services on the network, resolves their models, and routes requests to the best available backend. If a service fails, the circuit breaker opens and requests fail over to the next service by priority.

## Direct Mode

Skip mDNS discovery and connect to a known endpoint:

```typescript
const saturn = createSaturnProvider({
  direct: { baseURL: 'http://localhost:11434/v1' }
})
```

## Event Callbacks

React to services appearing and disappearing on the network:

```typescript
const saturn = createSaturnProvider({
  timeout: 5000,
  onServiceFound: (service) => console.log(`Found: ${service.name}`),
  onServiceLost: (service) => console.log(`Lost: ${service.name}`)
})
```

## Model References

Models are referenced as `service/model`:

```typescript
saturn('ollama/llama3.2')
saturn('openrouter/anthropic/claude-3.5-sonnet')
```

If no service is specified, the provider selects the best available service that offers the requested model.
