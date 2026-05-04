# Implementations

Saturn ships seven reference implementations across five languages and four mDNS libraries (Saturn.md:976). None share Saturn-specific code; conformance is the wire format.

A post-thesis [OpenCode fork](https://github.com/jperrello/opencode-saturn) (TypeScript) is also Saturn-aware but lives outside the monorepo and is not counted among the canonical seven.

## Feature matrix

| Feature | Go (`saturnd`) | Python (`saturn-ai`) | Rust (`saturn-router`) | TypeScript (`ai-sdk-provider-saturn`) | Lua (`vlc_extension`) | CLI (`saturn`) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Browse `_saturn._tcp.local.` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Resolve SRV+TXT | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Publish (run a responder) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Priority sort + failover | ✓ | ✓ | ✓ | ✓ | partial | ✓ |
| Cloud beacon (mint JWT) | partial | ✓ | ✗ | ✗ | ✗ | ✓ |
| OpenAI HTTP client built-in | ✗ | ✓ | ✗ | ✓ | ✓ | — |
| Cross-compiles to MIPS / OpenWRT | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| MCP surface | ✓ | ✓ | ✗ | ✗ | ✗ | — |

## The same five lines in every language

Each implementation discovers the highest-priority Saturn instance and prints its endpoint. Compare side-by-side:

=== "Go"

    ```go
    package main
    import ( "context"; "fmt"; "github.com/grandcat/zeroconf" )
    func main() {
        r, _ := zeroconf.NewResolver(nil)
        ch := make(chan *zeroconf.ServiceEntry)
        go r.Browse(context.Background(), "_saturn._tcp", "local.", ch)
        for e := range ch { fmt.Println(e.HostName, e.Port, e.Text) }
    }
    ```

=== "Python"

    ```python
    from saturn import discover, select_best_service
    services = discover(timeout=2.0)
    best = select_best_service(services)
    print(best.effective_endpoint)
    ```

=== "Rust"

    ```rust
    use mdns_sd::{ServiceDaemon, ServiceEvent};
    let mdns = ServiceDaemon::new().unwrap();
    let recv = mdns.browse("_saturn._tcp.local.").unwrap();
    while let Ok(ServiceEvent::ServiceResolved(s)) = recv.recv() {
        println!("{} {}:{}", s.get_fullname(), s.get_hostname(), s.get_port());
    }
    ```

=== "TypeScript"

    ```ts
    import { createSaturn } from "ai-sdk-provider-saturn";
    const saturn = createSaturn();
    const services = await saturn.discover({ timeout: 2000 });
    console.log(services[0].endpoint);
    ```

=== "CLI"

    ```bash
    $ saturn endpoint
    http://macbook.local:11434
    ```

## Per-language deep dives

### [Go — `saturnd`](../reference/clients/clients/cli/cli.md)

Standalone daemon under `saturnd/`. Browses mDNS, parses TXT, re-exports discovered backends over HTTP and MCP. Built with `grandcat/zeroconf`. No Python required.

```bash
$ cd saturnd && go build -o saturnd ./cmd/saturnd && ./saturnd
$ curl http://localhost:7827/v1/agents
```

→ [`reference/clients/cli/cli.md`](../reference/clients/cli/cli.md)

### [Python — `saturn-ai`](../reference/clients/python/api.md)

Reference package on PyPI. Ships the discovery library, server runtime, beacon, CLI, and Web UI. The Python SDK is the canonical implementation against which other clients are tested.

```bash
$ pip install saturn-ai
$ saturn discover
```

→ [`reference/clients/python/api.md`](../reference/clients/python/api.md)

### [Rust — `saturn-router`](../reference/clients/rust-router.md)

Cross-compiles to `mipsel-unknown-linux-musl` (~2 MB binary, 128 MB RAM target). Designed for router-edge deployment on OpenWRT — "DHCP for AI", literally.

→ [`reference/clients/rust-router.md`](../reference/clients/rust-router.md)

### [TypeScript — `ai-sdk-provider-saturn`](../reference/clients/typescript-api.md)

Drop-in [Vercel AI SDK](https://sdk.vercel.ai) provider. Adds discovery, circuit breaking, and failover to any AI SDK consumer.

→ [`reference/clients/typescript-api.md`](../reference/clients/typescript-api.md)

### Lua — `vlc_extension`

Bridges Saturn into VLC via the `dns-sd` CLI. Demonstrates the protocol in a non-AI-native host application — same wire format, no shared code with the Python or Go implementations.

→ Source: [`vlc_extension/`](https://github.com/jperrello/Saturn/tree/main/vlc_extension)

### MCP surface — `saturn-mcp`

Surfaces Saturn discovery as MCP tools so any MCP-aware agent (Claude Desktop, Cursor, Open WebUI) can browse the LAN without protocol-specific code.

→ [`reference/clients/mcp-tools.md`](../reference/clients/mcp-tools.md)

### Open WebUI — `owui_saturn.py`

Single-file backend swap that points Open WebUI at the highest-priority Saturn endpoint.

→ [`integrations/open-webui.md`](../integrations/open-webui.md)

## Adding a new implementation

The wire format is the contract. To add a sixth language:

1. Browse `_saturn._tcp.local.` with any DNS-SD library.
2. Resolve SRV+TXT for instances you care about.
3. Validate `version=1` and parse the [TXT keys](../reference/protocol/txt-keys.md).
4. Sort by `priority`, pick the lowest healthy.
5. Send HTTP requests to `api_base` (or constructed `host:port`) per the [HTTP API](../reference/protocol/http-api.md).

That is the entire protocol surface. → [Spec v0.2](../spec/v0.2/wire-format.md)
