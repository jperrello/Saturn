# Discovery Flow

Saturn discovery is a 4-step sequence: browse, resolve, select, connect.

## Steps

<svg class="saturn-diagram" viewBox="0 0 650 480" xmlns="http://www.w3.org/2000/svg" width="650" height="480" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="650" height="480" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-accent" x="30" y="20" width="120" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="90" y="55" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">1. Browse</text>
  <text class="diagram-text" x="90" y="75" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">PTR query</text>
  <text class="diagram-text" x="180" y="55" text-anchor="start" font-size="12" fill="rgb(243,243,243)">Query _saturn._tcp.local. — all beacons</text>
  <text class="diagram-text" x="180" y="75" text-anchor="start" font-size="12" fill="rgb(243,243,243)">respond with instance names.</text>
  <line class="diagram-line" x1="90" y1="100" x2="90" y2="130" stroke-width="2" marker-end="url(#arrow2)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-accent" x="30" y="130" width="120" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="90" y="165" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">2. Resolve</text>
  <text class="diagram-text" x="90" y="185" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">SRV + TXT</text>
  <text class="diagram-text" x="180" y="165" text-anchor="start" font-size="12" fill="rgb(243,243,243)">For each instance, retrieve SRV record</text>
  <text class="diagram-text" x="180" y="185" text-anchor="start" font-size="12" fill="rgb(243,243,243)">(hostname, port) and TXT record (metadata).</text>
  <line class="diagram-line" x1="90" y1="210" x2="90" y2="240" stroke-width="2" marker-end="url(#arrow2)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-accent" x="30" y="240" width="120" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="90" y="275" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">3. Select</text>
  <text class="diagram-text" x="90" y="295" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">Sort + filter</text>
  <text class="diagram-text" x="180" y="275" text-anchor="start" font-size="12" fill="rgb(243,243,243)">Sort by priority (ascending). Optionally filter</text>
  <text class="diagram-text" x="180" y="295" text-anchor="start" font-size="12" fill="rgb(243,243,243)">by features or deployment type.</text>
  <line class="diagram-line" x1="90" y1="320" x2="90" y2="350" stroke-width="2" marker-end="url(#arrow2)" stroke="rgb(158,158,158)"/>
  <rect class="diagram-accent" x="30" y="350" width="120" height="80" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="90" y="385" text-anchor="middle" font-weight="bold" fill="rgb(243,243,243)">4. Connect</text>
  <text class="diagram-text" x="90" y="405" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">HTTP request</text>
  <text class="diagram-text" x="180" y="375" text-anchor="start" font-size="12" fill="rgb(243,243,243)">Cloud: use api_base + ephemeral_key as Bearer.</text>
  <text class="diagram-text" x="180" y="395" text-anchor="start" font-size="12" fill="rgb(243,243,243)">Local/network: construct URL from SRV record:</text>
  <text class="diagram-text" x="180" y="415" text-anchor="start" font-size="12" font-family="monospace" fill="rgb(243,243,243)">http://{host}:{port}/v1</text>
  <defs>
    <marker id="arrow2" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-line" points="0 0, 10 3.5, 0 7" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

### 1. Browse

Client queries PTR records for `_saturn._tcp.local.`. All beacons on the local network respond with their instance names.

### 2. Resolve

For each instance, the client retrieves the SRV record (hostname, port) and TXT record (metadata including `api_type`, `deployment`, `priority`, and optionally `ephemeral_key`).

### 3. Select

Sort discovered services by `priority` (ascending -- lower is preferred). Optionally filter by `features` or `deployment` type depending on application requirements.

### 4. Connect

Connection method depends on deployment type:

- **Cloud**: use `api_base` from TXT record as the endpoint. Set `Authorization: Bearer {ephemeral_key}` header.
- **Local / Network**: construct the URL from the SRV record: `http://{host}:{port}/v1`.

## Inspecting the wire

To verify a service is broadcasting, query the LAN with the standard `dns-sd` tool:

```bash
dns-sd -B _saturn._tcp local.
```

Every Saturn service on the network responds. This works without any Saturn implementation installed and is the canonical way to confirm beacon visibility independent of language or runtime.

## Implementations

Saturn discovery is implemented as a library in several languages. Each one wraps the four steps above so applications can call a single `discover()`-style function.

- [Python — saturn-ai package](../python-package.md) — convenient way to participate from Python (`pip install saturn-ai`)
- [TypeScript — AI SDK Provider](ai-sdk-provider.md)
- [Rust — Saturn Router](router.md)

All three speak the same protocol on the wire. A Python beacon is discoverable by a TypeScript client and vice versa.
