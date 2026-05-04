# Wire format

Saturn registers under `_saturn._tcp.local.` per [DNS-SD (RFC 6763)](https://datatracker.ietf.org/doc/html/rfc6763) over [mDNS (RFC 6762)](https://datatracker.ietf.org/doc/html/rfc6762). Three DNS record types form the discovery triple: PTR, SRV, TXT.

## The triple

```
PTR     _saturn._tcp.local.                 →  ollama._saturn._tcp.local.
                                            →  openrouter._saturn._tcp.local.

SRV     ollama._saturn._tcp.local.          →  macbook.local. port 11434
                                               (priority 0 weight 0 — unused by Saturn)

TXT     ollama._saturn._tcp.local.          →  version=1
                                               api_type=openai
                                               deployment=local
                                               priority=10
                                               features=chat,vision
```

A single PTR query for `_saturn._tcp.local.` returns every Saturn instance on the LAN. Modern resolvers (Bonjour, Avahi, `python-zeroconf`, `mdns-sd`, `multicast-dns`, `grandcat/zeroconf`) collapse the PTR + SRV + TXT exchange into one call.

## TXT record schema

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `version` | int | yes | — | Currently `1`. |
| `api_type` | enum | yes | — | `openai` (default), `ollama`, vendor-specific. |
| `deployment` | enum | yes | — | `local` \| `cloud` \| `network`. |
| `priority` | int | yes | — | Lower preferred. Distinct from SRV priority. |
| `api_base` | URL | when `deployment=cloud` | — | Required for cloud; forbidden otherwise. |
| `ephemeral_key` | JWT | when `deployment=cloud` | — | Sent to upstream as `Authorization: Bearer …`. |
| `rotation_interval` | int (seconds) | when `ephemeral_key` set | `300` | Reference Python beacon default. |
| `features` | comma-list | no | — | E.g. `chat,tools,vision,embeddings,streaming`. |

Full RFC-style stability and per-key prose: [TXT keys reference](txt-keys.md).

## Endpoint requirements

Every Saturn responder MUST serve three OpenAI-compatible HTTP routes:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness probe (`saturn/web.py:705-707`). |
| `GET` | `/v1/models` | Model enumeration. |
| `POST` | `/v1/chat/completions` | Chat completion; SSE streaming via `text/event-stream`. |

> **Doc drift note.** Earlier docs and Saturn.md:531–532 cite `/health`. The deployed reference implementation serves `/v1/health` (saturn/web.py:705–707); treat `/health` as historical. The `/v1/` prefix is now normative across all three routes.

## TXT size constraint

[RFC 6763 §6.1](https://datatracker.ietf.org/doc/html/rfc6763#section-6.1) caps each TXT character-string at 255 bytes. This is the binding reason Saturn ships JWT credentials in `ephemeral_key` rather than X.509 certificates: a 10-minute JWT fits in one string; a typical certificate chain does not. The total TXT record holds many strings, but interoperability with Apple Bonjour suggests keeping the cumulative size well below 1300 bytes to avoid mDNS fragmentation.

## A real exchange

Captured against a single Ollama Saturn responder on a quiet LAN:

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

Four UDP packets, 27 ms wall-clock from PTR query to SRV+TXT answer.

→ [TXT keys (RFC-style)](txt-keys.md) · [Discovery flow](discovery.md) · [HTTP API](http-api.md) · [Beacons](beacons.md) · [Security model](security.md)
