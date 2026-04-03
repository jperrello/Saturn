# Priority Routing

Saturn uses a priority-based system to select the best available service when multiple backends are on the network.

## How priority works

Each service registers with a numeric priority. **Lower numbers = higher priority** (priority 1 beats priority 10, which beats priority 50).

When a client needs a service:

1. Discovers all available services via mDNS
2. Filters by health status
3. Sorts by priority (ascending)
4. Routes to the lowest-priority-number healthy service

<svg class="saturn-diagram" viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg" width="600" height="300" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="600" height="300" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <rect class="diagram-accent" x="40" y="40" width="200" height="50" rx="6" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="140" y="60" text-anchor="middle" font-size="13" font-weight="bold" fill="rgb(243,243,243)">GPU Server</text>
  <text class="diagram-text" x="140" y="78" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">priority: 1</text>
  <rect class="diagram-box" x="40" y="120" width="200" height="50" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="140" y="140" text-anchor="middle" font-size="13" font-weight="bold" fill="rgb(243,243,243)">Cloud Primary</text>
  <text class="diagram-text" x="140" y="158" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">priority: 10</text>
  <rect class="diagram-box" x="40" y="200" width="200" height="50" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="140" y="220" text-anchor="middle" font-size="13" font-weight="bold" fill="rgb(243,243,243)">Cloud Fallback</text>
  <text class="diagram-text" x="140" y="238" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">priority: 50</text>
  <rect class="diagram-box" x="400" y="100" width="150" height="50" rx="6" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="475" y="130" text-anchor="middle" font-size="13" font-weight="bold" fill="rgb(243,243,243)">Client</text>
  <line class="diagram-accent" x1="400" y1="115" x2="245" y2="65" stroke-width="2.5" marker-end="url(#arrow-accent)" stroke="rgb(59,130,246)"/>
  <text class="diagram-text" x="340" y="80" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">active</text>
  <line class="diagram-line" x1="400" y1="130" x2="245" y2="145" stroke-width="1.5" stroke-dasharray="6,4" marker-end="url(#arrow-line)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="340" y="145" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">failover 1</text>
  <line class="diagram-line" x1="400" y1="145" x2="245" y2="225" stroke-width="1.5" stroke-dasharray="6,4" marker-end="url(#arrow-line)" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="355" y="205" text-anchor="middle" font-size="10" fill="rgb(243,243,243)">failover 2</text>
  <defs>
    <marker id="arrow-accent" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-accent" points="0 0, 10 3.5, 0 7" fill="rgb(59,130,246)"/>
    </marker>
    <marker id="arrow-line" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon class="diagram-line" points="0 0, 10 3.5, 0 7" fill="rgb(158,158,158)"/>
    </marker>
  </defs>
</svg>

The client always routes to the GPU Server (priority 1). If it goes down, traffic shifts to Cloud Primary (priority 10). If that also fails, Cloud Fallback (priority 50) handles requests.

## Health monitoring

Saturn polls `/v1/health` on each service every 20 seconds. A service is marked unhealthy after a failed health check and excluded from routing until it passes again.

The health check cycle:

1. Send GET to `/v1/health` on the service
2. Expect a 200 response within the timeout
3. Mark healthy or unhealthy accordingly
4. Repeat every 20 seconds

## Automatic failover

When the primary (lowest priority number) service goes down:

1. Health check detects the failure within 20 seconds
2. Next-lowest-priority healthy service becomes active
3. Traffic routes to the new active service immediately
4. When the primary recovers and passes a health check, routing switches back automatically

No manual intervention required. Recovery is automatic.

## Auto recovery

When a failed service comes back online, Saturn detects it on the next health poll. The service re-enters the pool at its configured priority. If its priority is lower (more preferred) than the current active service, it takes over immediately.

## Priority conflict resolution

When a new server starts, it checks existing priorities on the network via mDNS discovery. If another service already has the same priority, the new service auto-increments to the next available value.

For example: if you start a service with `priority = 10` and another service already has priority 10, your service registers as priority 11.

## Recommended priority layout

| Range | Use |
|-------|-----|
| 1--9 | Local GPU servers, fastest/cheapest resources |
| 10--29 | Primary cloud services |
| 30--49 | Secondary cloud services |
| 50--89 | Backup services |
| 90--99 | Fallback and error handlers |
