# Discovery flow

A conformant Saturn client performs four steps. The four are mechanical — every reference implementation does them the same way.

## 1. Browse

Send a PTR query for `_saturn._tcp.local.` to multicast address 224.0.0.251 (IPv4) or `ff02::fb` (IPv6) on UDP/5353. Every Saturn responder on the broadcast domain answers with its instance name.

=== "curl/CLI"

    ```bash
    $ dns-sd -B _saturn._tcp .local
    Browsing for _saturn._tcp.local
      Add  3 ollama._saturn._tcp.local.
      Add  3 openrouter._saturn._tcp.local.
    ```

=== "Go"

    ```go
    r, _ := zeroconf.NewResolver(nil)
    ch := make(chan *zeroconf.ServiceEntry)
    go r.Browse(ctx, "_saturn._tcp", "local.", ch)
    ```

=== "Python"

    ```python
    from saturn import discover
    services = discover(timeout=2.0)
    ```

## 2. Resolve

For each instance, send SRV + TXT queries. SRV gives `host:port`; TXT gives the Saturn metadata. Most resolvers issue both as a single mDNS message and aggregate the answer.

=== "curl/CLI"

    ```bash
    $ dns-sd -L "ollama" _saturn._tcp local.
    ollama._saturn._tcp.local. can be reached at macbook.local.:11434
      version=1 api_type=openai deployment=local priority=10 features=chat,tools
    ```

=== "Python"

    ```python
    s = services[0]
    print(s.host, s.port, s.txt)
    ```

## 3. Select

Sort discovered services by the TXT `priority` field, ascending — lower is preferred. Optionally filter by `features` (e.g. only route a vision request to instances advertising `vision`) or `deployment` (e.g. require `deployment=local` for privacy-sensitive prompts). Pick the first healthy match.

```python
ranked = sorted(services, key=lambda s: int(s.txt["priority"]))
for s in ranked:
    if probe(s):                 # GET /v1/health, see step 4
        chosen = s
        break
```

The SRV record carries its own `priority` and `weight` fields per RFC 2782; Saturn does **not** use them. Use the TXT `priority` only.

## 4. Connect

Connection method depends on `deployment`:

- **`deployment=local`** or **`network`** — construct the URL from the SRV: `http://<host>:<port>`.
- **`deployment=cloud`** — use the TXT `api_base` directly. Send the TXT `ephemeral_key` as `Authorization: Bearer <key>`.

```bash
# local / network
$ curl http://macbook.local:11434/v1/chat/completions \
       -H 'Content-Type: application/json' \
       -d '{"model":"llama3","messages":[{"role":"user","content":"hi"}]}'

# cloud (beacon-supplied)
$ curl https://openrouter.ai/api/v1/chat/completions \
       -H "Authorization: Bearer $EPHEMERAL_KEY" \
       -H 'Content-Type: application/json' \
       -d '{"model":"anthropic/claude-3.5-sonnet","messages":[...]}'
```

Health check first if you care about failover: `GET /v1/health` → `200 OK` + `{"status":"ok"}`.

## Failover

When `GET /v1/health` returns non-200 or times out, fall through to the next instance in the priority-sorted list. The reference TypeScript provider (`ai-sdk-provider-saturn`) uses a circuit-breaker per instance to suppress flapping. The reference Python client retries every 20 s.

## End-to-end timing

On a quiet LAN, browse + resolve completes in tens of milliseconds. The reference Python client's `discover(timeout=2.0)` waits 2 s for late responders; lower the timeout if you only need the first answer.

→ [Wire format](wire-format.md) · [HTTP API](http-api.md) · [TXT keys](txt-keys.md)
