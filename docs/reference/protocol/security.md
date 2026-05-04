# Security Model

Saturn operates on a zero-configuration trust model. This page describes what it protects against, what it does not, and why.

## Threat Model 1: Corporate Data Collection

**Scenario**: A user does not want cloud AI providers collecting their prompts.

**Mitigation**: The network administrator deploys a local inference server (e.g., Ollama) and configures its Saturn beacon with a higher priority (lower number) than any cloud service. Discovery returns the local service first. Prompts never leave the LAN.

**Limitation**: Requires local hardware capable of running models that match the cloud provider's quality. A laptop GPU running a 7B model is not equivalent to GPT-4.

## Threat Model 2: Untrusted Administrator

**Scenario**: The network administrator might log traffic or advertise a malicious endpoint.

Two sub-cases:

**Admin runs only a beacon** (pointing to a legitimate cloud endpoint). The admin cannot see prompt content. Traffic flows directly from the client to the cloud endpoint. The admin sees only mDNS traffic (service names, metadata), not HTTP payloads.

**Admin controls both beacon and endpoint**. The admin has full access to all prompts and responses. Saturn cannot protect against this without user-level authentication, which would destroy zero-configuration.

This is the same trust model as connecting to office WiFi. If you don't trust the network operator, you need a VPN or a service with end-to-end encryption -- neither of which Saturn provides.

## Broadcast Exposure

Any device on the LAN can observe mDNS announcements. For cloud deployments, the TXT record contains the ephemeral API key in plaintext.

Exposure is bounded by:

- **Ephemeral key lifecycle**: keys expire within 10 minutes (default). An attacker must extract and use the key before expiration.
- **Admin spending limits**: cloud provider accounts should have spending caps. Even if a key is abused during its lifetime, damage is bounded by the provider's rate limits and the admin's budget.

For stronger network-layer guarantees, VLAN segmentation or 802.1X port-based authentication can restrict which devices see mDNS traffic. These are standard network controls outside Saturn's scope.
