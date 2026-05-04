# Beacons

A beacon is a Saturn process that advertises AI services over mDNS. There are two types, distinguished by how they handle credentials.

## Key Rotation Timeline

<svg class="saturn-diagram" viewBox="0 0 700 200" xmlns="http://www.w3.org/2000/svg" width="700" height="200" style="display:block;margin:2rem auto;max-width:100%;">
  <rect class="diagram-bg" x="0" y="0" width="700" height="200" rx="8" fill="rgb(23,23,23)" stroke="none"/>
  <line class="diagram-line" x1="50" y1="100" x2="650" y2="100" stroke-width="2" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="100" y1="90" x2="100" y2="110" stroke-width="2" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="100" y="130" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">t=0</text>
  <line class="diagram-line" x1="300" y1="90" x2="300" y2="110" stroke-width="2" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="300" y="130" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">t=5min</text>
  <line class="diagram-line" x1="500" y1="90" x2="500" y2="110" stroke-width="2" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="500" y="130" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">t=10min</text>
  <rect class="diagram-accent" x="100" y="55" width="400" height="20" rx="4" opacity="0.7" fill="rgb(59,130,246)"/>
  <text class="diagram-text" x="300" y="70" text-anchor="middle" font-size="11" font-weight="bold" fill="rgb(243,243,243)">Key A (generated t=0, expires t=10min)</text>
  <rect class="diagram-box" x="300" y="30" width="400" height="20" rx="4" opacity="0.7" fill="rgb(37,37,37)" stroke="rgba(255,255,255,0.1)"/>
  <text class="diagram-text" x="500" y="45" text-anchor="middle" font-size="11" font-weight="bold" fill="rgb(243,243,243)">Key B (generated t=5min, expires t=15min)</text>
  <line class="diagram-line" x1="300" y1="150" x2="500" y2="150" stroke-width="1" stroke-dasharray="4" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="300" y1="145" x2="300" y2="155" stroke-width="1" stroke="rgb(158,158,158)"/>
  <line class="diagram-line" x1="500" y1="145" x2="500" y2="155" stroke-width="1" stroke="rgb(158,158,158)"/>
  <text class="diagram-text" x="400" y="170" text-anchor="middle" font-size="11" fill="rgb(243,243,243)">Overlap window (both keys valid)</text>
</svg>

## Beacon Types

### Local Beacon

Announces a local service (e.g., Ollama running on localhost). The TXT record contains `deployment=local` and the SRV record points to the machine running the inference server. No ephemeral keys are needed -- the service is on the local network and requires no authentication.

### Cloud Beacon

Bridges to a remote API provider (OpenRouter, DeepInfra, etc.). The beacon:

1. Generates an ephemeral API key
2. Broadcasts the key in the TXT record (`ephemeral_key` field)
3. Deletes the key after its expiration interval

Clients read the ephemeral key from mDNS and use it directly as a Bearer token against the `api_base` URL.

## Default Lifecycle

- **Key lifetime**: 10 minutes (`expiration_interval`)
- **Rotation interval**: 5 minutes (`rotation_interval`)
- **Overlap window**: 5 minutes where both the old and new key are valid

The overlap ensures seamless handoff. A client that discovered Key A at t=4min can still use it until t=10min, even though Key B was broadcast at t=5min.

## Why Ephemeral Keys

Meli et al. found over 100,000 GitHub repositories with leaked API secrets. Static key mitigations (revocation, scanning) act after the damage is done. Ephemeral keys invert the problem: a key extracted from a packet capture expires within 10 minutes. By the time an attacker extracts and attempts to use it, the key is already invalid.

## Trade-off

The beacon must maintain an active session with the cloud provider's key provisioning API. If the beacon loses internet connectivity, existing keys expire without replacement. Clients will fail over to other services (local or other beacons) based on priority ordering.
