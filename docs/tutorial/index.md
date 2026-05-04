# Tutorial — build a discovery-aware client end to end

~30 minutes. By the end you will have:

1. A Saturn responder published from one terminal.
2. A second terminal that browses, resolves, picks the highest-priority instance, and sends a chat completion to it.
3. A working understanding of every step on the wire.

If you only want to *use* a Saturn endpoint somebody else published, see the [Quickstart](../getting-started/quickstart.md) — it takes five minutes and skips the responder side.

## Prerequisites

- macOS or Linux on the same LAN segment for both terminals (no AP isolation).
- One of: `dns-sd` (macOS, ships with the OS) or `avahi-utils` (Linux: `sudo apt install avahi-utils`).
- An OpenAI-compatible HTTP server you control. The simplest option is a local [Ollama](https://ollama.ai) install with one small model pulled (`ollama pull llama3.2`).

## Part 1 — Publish a responder (terminal A)

The minimum viable Saturn responder is "advertise an instance over Bonjour/Avahi pointing at an existing OpenAI-compatible HTTP server." We will use raw OS tools, no Saturn-specific binary, to underline that the protocol is the contract.

=== "macOS"

    ```bash
    # Ollama listens on 11434 by default; confirm it's up:
    $ curl -s http://localhost:11434/api/version
    {"version":"0.3.12"}

    # Publish ourselves as a Saturn instance.
    # dns-sd -R: register a service.
    $ dns-sd -R "ollama" _saturn._tcp local 11434 \
        version=1 api_type=openai deployment=local priority=10 features=chat
    Registering Service ollama._saturn._tcp.local. port 11434
    Got a reply for service ollama._saturn._tcp.local.: Name now registered and active
    ```

=== "Linux"

    ```bash
    $ ollama serve &
    $ avahi-publish -s "ollama" _saturn._tcp 11434 \
        version=1 api_type=openai deployment=local priority=10 features=chat
    Established under name 'ollama'
    ```

Leave that command running. It is the responder; closing it withdraws the advertisement.

## Part 2 — Verify the wire (any terminal)

Before writing client code, verify the publication landed. In a third terminal (or background the publisher first):

```bash
$ dns-sd -B _saturn._tcp .local
Browsing for _saturn._tcp.local
  Add  3 ollama._saturn._tcp.local.

$ dns-sd -L "ollama" _saturn._tcp local.
ollama._saturn._tcp.local. can be reached at <hostname>.local.:11434
  version=1 api_type=openai deployment=local priority=10 features=chat
```

If you see those two answers, every Saturn client on the LAN can now find your responder. The rest of this tutorial is consumer-side.

## Part 3 — Write the client (terminal B)

Goal: a 30-line program that browses, resolves, picks by priority, and sends a chat completion. We will write it three ways. Pick the language you actually use; the others are there to show the protocol is identical regardless.

=== "Go"

    Save as `client.go`, run with `go run client.go`.

    ```go
    package main

    import (
        "bytes"
        "context"
        "encoding/json"
        "fmt"
        "io"
        "net/http"
        "sort"
        "strconv"
        "time"

        "github.com/grandcat/zeroconf"
    )

    type service struct {
        host     string
        port     int
        priority int
    }

    func main() {
        r, _ := zeroconf.NewResolver(nil)
        ch := make(chan *zeroconf.ServiceEntry)
        ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
        defer cancel()
        go r.Browse(ctx, "_saturn._tcp", "local.", ch)

        var found []service
        for e := range ch {
            p := 9999
            for _, t := range e.Text {
                if len(t) > 9 && t[:9] == "priority=" {
                    p, _ = strconv.Atoi(t[9:])
                }
            }
            found = append(found, service{e.HostName, e.Port, p})
        }
        if len(found) == 0 { panic("no Saturn services") }
        sort.Slice(found, func(i, j int) bool { return found[i].priority < found[j].priority })

        url := fmt.Sprintf("http://%s:%d/v1/chat/completions", found[0].host, found[0].port)
        body, _ := json.Marshal(map[string]any{
            "model": "llama3.2",
            "messages": []map[string]string{{"role":"user","content":"hi"}},
        })
        resp, _ := http.Post(url, "application/json", bytes.NewReader(body))
        out, _ := io.ReadAll(resp.Body)
        fmt.Println(string(out))
    }
    ```

=== "Python"

    Save as `client.py`, run with `python3 client.py`.

    ```python
    from saturn import discover, select_best_service
    from openai import OpenAI

    services = discover(timeout=2.0)
    if not services:
        raise SystemExit("no Saturn services on the LAN")

    best = select_best_service(services)
    print(f"using {best.name} → {best.effective_endpoint}")

    client = OpenAI(base_url=best.effective_endpoint, api_key="unused")
    resp = client.chat.completions.create(
        model="llama3.2",
        messages=[{"role": "user", "content": "hi"}],
    )
    print(resp.choices[0].message.content)
    ```

=== "TypeScript"

    Save as `client.ts`, run with `npx tsx client.ts`.

    ```ts
    import { createSaturn } from "ai-sdk-provider-saturn";
    import { generateText } from "ai";

    const saturn = createSaturn();
    const services = await saturn.discover({ timeout: 2000 });
    if (!services.length) throw new Error("no Saturn services on the LAN");

    const best = services.sort((a, b) => a.priority - b.priority)[0];
    console.log(`using ${best.name} → ${best.endpoint}`);

    const { text } = await generateText({
        model: saturn.chat(best.name, "llama3.2"),
        prompt: "hi",
    });
    console.log(text);
    ```

## Part 4 — Add a second responder, verify priority routing

Open another terminal and publish a second instance with a *higher* priority number (so lower preference):

```bash
$ dns-sd -R "ollama-secondary" _saturn._tcp local 11434 \
    version=1 api_type=openai deployment=local priority=50
```

Re-run the client from Part 3. The output should still print `ollama` (priority 10), not `ollama-secondary` (priority 50). Now stop the primary responder (Ctrl-C terminal A). Re-run the client. It should print `ollama-secondary`. You have just verified failover.

## Part 5 — Add a TXT field, verify the client ignores unknown keys

Re-publish the primary responder with one extra key:

```bash
$ dns-sd -R "ollama" _saturn._tcp local 11434 \
    version=1 api_type=openai deployment=local priority=10 features=chat \
    region=basement
```

The client should still work unchanged. This is the forward-compatibility property: browsers MUST ignore unknown TXT keys. → [TXT keys reference](../reference/protocol/txt-keys.md)

## What just happened

You published two Saturn instances using stock OS tools, browsed them with the same OS tools, wrote a 30-line client in your language of choice that did the full browse → resolve → select → connect cycle, and verified priority routing and forward-compatibility on the wire. Every step was governed by the wire format alone — no Saturn-specific shared code between the responder, the verifier, and the client.

## Where to go next

- [**Concepts: Saturn on the wire**](../concepts/protocol.md) — what those four packets actually contain.
- [**Reference: TXT keys**](../reference/protocol/txt-keys.md) — every field, RFC-style.
- [**Reference: discovery flow**](../reference/protocol/discovery.md) — full client loop including health checks and circuit breaking.
- [**Reference: beacons**](../reference/protocol/beacons.md) — when you want to advertise a *cloud* upstream instead of a local Ollama.
- [**Reference: security model**](../reference/protocol/security.md) — read this before pointing a beacon at a real cloud account.
