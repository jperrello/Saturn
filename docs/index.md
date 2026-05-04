# Saturn

**Local-network discovery for AI endpoints. Zero config, zero registry, RFC-grade.**

Saturn is a DNS-SD/mDNS protocol — service type `_saturn._tcp.local.` — for OpenAI-compatible AI backends on a LAN. Run a Saturn responder once on your home, lab, or office network; every device on that network discovers it the same way it discovers a printer.

- **Zero-config.** No accounts, no per-app keys, no manual endpoint URLs.
- **RFC-based.** [RFC 6762 (mDNS)](https://datatracker.ietf.org/doc/html/rfc6762) + [RFC 6763 (DNS-SD)](https://datatracker.ietf.org/doc/html/rfc6763). The wire format *is* the contract.
- **Multi-language.** Reference implementations in Go, Python, Rust, TypeScript, and Lua interoperate with no shared SDK.
- **Encrypted-aware.** Cloud backends ship 10-minute ephemeral JWTs in TXT records, rotated every 5 minutes.
- **Sub-second discovery** on a quiet LAN.

## See it work

=== "curl"

    ```bash
    $ dns-sd -B _saturn._tcp local.            # macOS / Bonjour
    Browsing for _saturn._tcp.local.
    Add  3   ollama       _saturn._tcp.   local.
    Add  3   openrouter   _saturn._tcp.   local.

    $ curl http://macbook.local:11434/v1/models
    {"object":"list","data":[{"id":"llama3.2","object":"model"}, ...]}
    ```

=== "Go"

    ```go
    // saturnd/cmd/saturnd — see implementations/go
    func main() {
        for s := range saturn.Browse(ctx, "_saturn._tcp.local.") {
            fmt.Printf("%s  prio=%d  %s\n", s.Name, s.Priority, s.URL())
        }
    }
    ```

=== "Python"

    ```python
    from saturn import discover
    for s in discover(timeout=2.0):
        print(s.name, s.priority, s.effective_endpoint)
    ```

=== "CLI"

    ```bash
    $ saturn discover
    ollama       prio=10  http://macbook.local:11434
    openrouter   prio=20  https://openrouter.ai/api/v1
    ```

[**Quickstart →**](getting-started/quickstart.md){ .md-button .md-button--primary }
[**Protocol Spec →**](reference/protocol/wire-format.md){ .md-button }

## Implementations

| Language | Package | mDNS library |
|---|---|---|
| [Go](implementations/index.md) | `saturnd/` | `grandcat/zeroconf` |
| [Python](implementations/index.md) | `saturn-ai` | `python-zeroconf` |
| [Rust](implementations/index.md) | `saturn-router` | `mdns-sd` |
| [TypeScript](implementations/index.md) | `ai-sdk-provider-saturn` | `multicast-dns` |
| [Lua](implementations/index.md) | `vlc_extension` | `dns-sd` CLI |
| [CLI](reference/clients/cli/cli.md) | `saturn` | — |

Seven artifacts across five languages and four mDNS libraries, sharing no Saturn-specific code (Saturn.md:976). Interoperability comes from the wire format alone.

## Three routes from here

- **Use Saturn** — point a tool at a discovered endpoint. → [Quickstart](getting-started/quickstart.md)
- **Build a client** — write code that browses `_saturn._tcp.local.` and routes by priority. → [Implementations](implementations/index.md)
- **Implement Saturn** — write a responder in a new language. → [Spec v0.2](spec/v0.2/wire-format.md)

## What is mDNS?

Multicast DNS is a UDP/5353 protocol that lets devices on a LAN answer DNS queries for each other without a central server. DNS-SD layers a service-discovery convention on top: a service type (`_saturn._tcp.local.`) maps to instance names (PTR), each instance resolves to a host/port (SRV), and metadata travels in key-value records (TXT). Bonjour and Avahi are the two dominant implementations; both are Saturn-compatible without modification. → [Concepts: protocol](concepts/protocol.md)

## Project status

Saturn is the artifact of a master's thesis at UC Santa Cruz (Joey Perrello, advised by Adam Smith). The thesis is in submission. Citations in this documentation reference the source manuscript by line number where applicable.
