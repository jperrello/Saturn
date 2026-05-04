# What Saturn looks like on the wire

Saturn is a profile of [DNS-SD (RFC 6763)](https://datatracker.ietf.org/doc/html/rfc6763) over [mDNS (RFC 6762)](https://datatracker.ietf.org/doc/html/rfc6762). Three DNS record types — PTR, SRV, TXT — carry every Saturn advertisement. There is no Saturn-specific transport, no Saturn handshake, and no Saturn registry. If you can send a UDP/5353 multicast and parse a DNS message, you can implement Saturn.

## A single discovery exchange

```
client                                      server (Saturn responder)
  │                                                   │
  │  PTR query: _saturn._tcp.local.    (224.0.0.251)  │
  │ ───────────────────────────────────────────────► │
  │                                                   │
  │  PTR answer: ollama._saturn._tcp.local.           │
  │ ◄─────────────────────────────────────────────── │
  │                                                   │
  │  SRV+TXT query: ollama._saturn._tcp.local.        │
  │ ───────────────────────────────────────────────► │
  │                                                   │
  │  SRV answer: macbook.local.  port 11434           │
  │  TXT answer: version=1 api_type=openai ...        │
  │ ◄─────────────────────────────────────────────── │
  │                                                   │
  │  HTTP GET http://macbook.local:11434/v1/models    │
  │ ───────────────────────────────────────────────► │
```

The first two messages are mDNS. The third is plain HTTP, not part of the Saturn protocol — Saturn ends once the client has a URL.

## The DNS-SD record triple

| Record | Owner name | Carries |
|---|---|---|
| **PTR** | `_saturn._tcp.local.` | Instance name(s) — one per service |
| **SRV** | `<instance>._saturn._tcp.local.` | Hostname + port + priority + weight |
| **TXT** | `<instance>._saturn._tcp.local.` | Key=value metadata (Saturn schema) |

A single PTR query returns every Saturn instance on the LAN. The client then issues SRV+TXT queries for the instances it wants. Modern resolvers (Bonjour, Avahi, `python-zeroconf`, `mdns-sd`) collapse this into one call.

## A real TXT record, byte-annotated

A Saturn TXT record is a sequence of DNS character-strings, each prefixed by a length octet. Below is one cloud-backend record as it travels on the wire:

```
            ┌──┐
length=11   │0B│  v e r s i o n = 1
            ├──┤
length=15   │0F│  a p i _ t y p e = o p e n a i
            ├──┤
length=18   │12│  d e p l o y m e n t = c l o u d
            ├──┤
length=12   │0C│  p r i o r i t y = 1 0
            ├──┤
length=33   │21│  a p i _ b a s e = h t t p s : / / o p e n r o u t e r . a i / a p i / v 1
            ├──┤
length=NN   │..│  e p h e m e r a l _ k e y = e y J h b G c i O i J ...
            ├──┤
length=22   │16│  r o t a t i o n _ i n t e r v a l = 3 0 0
            ├──┤
length=21   │15│  f e a t u r e s = c h a t , t o o l s , v i s i o n
            └──┘
```

Each string MUST be ≤ 255 bytes (RFC 6763 §6.1). This is why Saturn carries JWT credentials but not X.509 certificates: a 10-minute JWT fits in one string; a typical certificate chain does not. → [Reference: TXT keys](../reference/protocol/wire-format.md)

## Glossary

| Term | Meaning |
|---|---|
| **Service type** | The string `_saturn._tcp.local.` — distinguishes Saturn from every other DNS-SD service on the LAN. |
| **Instance** | A single Saturn responder. The instance name (e.g. `ollama`) is the user-facing label. |
| **Responder** | The process that publishes PTR/SRV/TXT records and answers HTTP requests on the advertised port. |
| **Browser** | A client that issues PTR queries and receives instance lists. |
| **Resolver** | A client that issues SRV/TXT queries to turn an instance name into a host/port/metadata triple. |
| **Beacon** | A responder that publishes credentials (`ephemeral_key`) for a cloud backend without proxying inference traffic. |
| **Priority** | A numeric hint in TXT (`priority=N`); browsers prefer lower values. Distinct from the SRV priority field, which is unused by Saturn. |

## Why mDNS, not a registry

A registry-based design (a centrally hosted "AI directory" service) would require operating the registry, authenticating to it, and propagating updates. mDNS already exists on every modern OS, requires no operator, and converges in milliseconds on a quiet LAN. The trade-off is a multicast trust assumption: any device on the same broadcast domain sees Saturn advertisements, including ephemeral credentials. Saturn treats this the way Bonjour treats printer queues — the network operator is the trust boundary. → [Concepts: mDNS background](mdns-background.md), [Reference: security model](../reference/protocol/security.md)

## How this looks on the wire (full capture)

```
$ tcpdump -nn -i en0 -s0 udp port 5353 -c 4
21:04:12.001  IP 10.0.0.5.5353  > 224.0.0.251.5353:
              0 PTR (QM)? _saturn._tcp.local. (37)
21:04:12.043  IP 10.0.0.7.5353  > 224.0.0.251.5353:
              0*- [0q] 1/0/3 PTR ollama._saturn._tcp.local. (180)
21:04:12.044  IP 10.0.0.5.5353  > 224.0.0.251.5353:
              0 SRV (QM)? ollama._saturn._tcp.local. (44)
21:04:12.071  IP 10.0.0.7.5353  > 224.0.0.251.5353:
              0*- [0q] 2/0/3 SRV macbook.local.:11434, TXT "version=1" "api_type=openai" ... (215)
```

→ [Quickstart: see this happen](../getting-started/quickstart.md) · [Reference: wire format](../reference/protocol/wire-format.md)
