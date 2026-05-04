# Quickstart

Get a working Saturn discovery exchange in five steps. Each step works against the same `_saturn._tcp.local.` advertisement; pick the language tab you prefer.

## 1. Confirm your OS speaks mDNS

Saturn rides on Bonjour (macOS, Windows + Bonjour Print Services) or Avahi (Linux). You almost certainly already have one.

=== "macOS"

    ```bash
    $ which dns-sd
    /usr/bin/dns-sd
    ```

=== "Linux"

    ```bash
    $ which avahi-browse || sudo apt install -y avahi-utils
    /usr/bin/avahi-browse
    ```

=== "Windows"

    Install [Bonjour Print Services](https://support.apple.com/kb/DL999). The `dns-sd` command lands in `%PROGRAMFILES%\Bonjour\`.

## 2. Browse the network for Saturn services

=== "curl/CLI"

    ```bash
    $ dns-sd -B _saturn._tcp local.            # macOS
    Browsing for _saturn._tcp.local.
    Add  3   ollama       _saturn._tcp.   local.

    $ avahi-browse -rtp _saturn._tcp           # Linux
    +;wlan0;IPv4;ollama;_saturn._tcp;local
    ```

=== "Go"

    ```go
    package main
    import ( "context"; "fmt"; "github.com/grandcat/zeroconf" )
    func main() {
        r, _ := zeroconf.NewResolver(nil)
        entries := make(chan *zeroconf.ServiceEntry)
        go r.Browse(context.Background(), "_saturn._tcp", "local.", entries)
        for e := range entries { fmt.Println(e.Instance, e.Port, e.Text) }
    }
    ```

=== "Python"

    ```python
    from saturn import discover
    for s in discover(timeout=2.0):
        print(s.name, s.host, s.port, s.priority)
    ```

If nothing appears, no responder is running on your LAN. Skip to step 5 to start one.

## 3. Resolve one instance to host + port + TXT

=== "curl/CLI"

    ```bash
    $ dns-sd -L "ollama" _saturn._tcp local.
    ollama._saturn._tcp.local. can be reached at macbook.local.:11434
      version=1 api_type=openai deployment=local priority=10 features=chat,tools
    ```

=== "Go"

    ```go
    // Inside the entries-channel loop:
    fmt.Printf("%s:%d  TXT=%v\n", e.HostName, e.Port, e.Text)
    ```

=== "Python"

    ```python
    s = next(iter(discover(timeout=2.0)))
    print(f"{s.host}:{s.port}  v={s.txt['version']}  prio={s.priority}")
    ```

The TXT record is the wire artifact you build clients against. → [TXT keys reference](../reference/protocol/wire-format.md)

## 4. Call the OpenAI-compatible endpoint

=== "curl"

    ```bash
    $ curl http://macbook.local:11434/v1/models
    {"object":"list","data":[{"id":"llama3.2","object":"model"}]}

    $ curl http://macbook.local:11434/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'
    ```

=== "Go"

    ```go
    resp, _ := http.Post(s.URL()+"/v1/chat/completions",
        "application/json",
        strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hi"}]}`))
    ```

=== "Python"

    ```python
    from openai import OpenAI
    c = OpenAI(base_url=s.effective_endpoint, api_key="unused")
    print(c.chat.completions.create(
        model="auto",
        messages=[{"role":"user","content":"hi"}]
    ).choices[0].message.content)
    ```

Any OpenAI-compatible client works — the discovered URL drops in as `base_url`.

## 5. Run your own responder

=== "curl/CLI"

    Use any Bonjour/Avahi tool that registers a service. Example with `avahi-publish`:

    ```bash
    $ avahi-publish -s ollama _saturn._tcp 11434 \
        version=1 api_type=openai deployment=local priority=10
    ```

=== "Go"

    ```bash
    $ cd saturnd && go build -o saturnd ./cmd/saturnd
    $ ./saturnd serve --backend http://localhost:11434 --priority 10
    ```

=== "Python"

    ```bash
    $ pip install saturn-ai
    $ saturn config new                # interactive — name, backend, priority
    $ saturn run ollama
    ```

The responder broadcasts on mDNS. Every device on the LAN now sees it via step 2.

---

## What just happened

You browsed `_saturn._tcp.local.`, resolved an SRV+TXT pair, and called an OpenAI-compatible HTTP endpoint. No accounts, no manual URLs, no per-app keys. The advertisement is reachable from any conformant mDNS stack — none of the steps above required Saturn-specific code.

## Next steps

- [**Tutorial**](../tutorial/index.md) — build a discovery-aware client end-to-end (~30 min).
- [**How-to: advertise a service**](../how-to/for-researchers.md) — task-shaped recipes.
- [**Protocol reference**](../reference/protocol/wire-format.md) — full TXT schema and endpoint contract.
