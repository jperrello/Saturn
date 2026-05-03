# Saturn Quickstart

**Saturn is a protocol, not a Python library.** It is the DNS-SD/mDNS
service type `_saturn._tcp.local.` plus a TXT-record schema (priority,
version, api, features, models). Any language that can speak mDNS and
HTTP can be a Saturn client or server.

This page gets you from "nothing on the network" to a working chat
completion in under five minutes, using whichever client you already
have. The Python `saturn` package, the Go `saturnd` daemon, and a raw
`curl + dns-sd` terminal session are equal peers — pick any.

## You need

- macOS or Linux on a network where mDNS works (home Wi-Fi or wired —
  not eduroam / corporate guest Wi-Fi, which block multicast).
- Some way to run a Saturn server. Any of:
  - the Python `saturn` CLI (this repo, `pip install -e .`)
  - the Go `saturnd` daemon (`saturnd/`, `go build ./cmd/saturnd`)
  - any other process that advertises `_saturn._tcp.local.` with a
    valid TXT record and serves OpenAI-compatible HTTP on the
    advertised port.
- An OpenAI-compatible backend behind it. The demo uses
  [Ollama](https://ollama.com/download). Replace with anything that
  speaks `/v1/chat/completions`.

No API key. No account. No subscription.

## Start a Saturn-advertised backend

For the rest of this page we assume a Saturn server is advertising
`ollama-8080._saturn._tcp.local.` on your LAN. The Python reference
implementation does this in one command:

```sh
saturn ollama
```

The Go daemon does the equivalent — see [saturnd's README](../saturnd/README.md).
The protocol does not care which one is running.

## Discover and use it — three equal clients

### 1. curl + dns-sd (no language, just the protocol)

```sh
# Browse the service type
dns-sd -B _saturn._tcp local. &

# Resolve the instance you saw in the browse output
dns-sd -L ollama-8080 _saturn._tcp local.
# -> reports hostname, port, and TXT records (priority=50, api=ollama, …)

# Resolve the hostname to an IP and call /v1/chat/completions
HOST=$(dns-sd -G v4 ollama-8080.local | awk '/IPv4/ {print $6; exit}')
curl -sS "http://$HOST:8080/v1/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"qwen2.5:0.5b","messages":[{"role":"user","content":"hi"}]}'
```

That's the full Saturn flow with no library at all. Linux users can
swap `dns-sd` for `avahi-browse -rt _saturn._tcp` and `getent ahosts`.

### 2. Go via saturnd

`saturnd` is the Go daemon for Saturn. It does the discovery and
exposes the result over a small HTTP API on `localhost:7827` so other
processes can stay simple.

```sh
# in one terminal
saturnd --verbose

# in another
curl -sS http://localhost:7827/v1/agents | jq '.'
ENDPOINT=$(curl -sS http://localhost:7827/v1/agents \
  | jq -r '.agents[0].endpoint')
curl -sS "$ENDPOINT/v1/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"qwen2.5:0.5b","messages":[{"role":"user","content":"hi"}]}'
```

Inside a Go program, the same idea is a `net/http` GET against
`localhost:7827/v1/agents` plus a `POST` against the returned endpoint.
No mDNS code on the caller side — `saturnd` does it.

### 3. JavaScript / browser fetch

Browsers can't speak mDNS, but once a Saturn endpoint is known (via
saturnd, the Web UI's discovery, or a configured fallback), a plain
`fetch` works:

```js
// pick up the endpoint however your app got it — for the Saturn Web UI
// it is window.location.origin since the UI is itself a Saturn proxy
const base = window.location.origin

const r = await fetch(`${base}/v1/chat/completions`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    model: 'qwen2.5:0.5b',
    messages: [{ role: 'user', content: 'hi' }],
  }),
})
console.log(await r.json())
```

The Web UI in this repo uses exactly this pattern — see
`Web-UI/app.js`'s `saturnEndpoint()` helper.

### 4. Python (one implementation among many)

The Python `saturn` package is a reference implementation. It ships
its own mDNS browser so your app code does not have to.

```python
import json, subprocess, urllib.request

base = subprocess.check_output(["saturn", "endpoint"], text=True).strip()
req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=json.dumps({
        "model": "qwen2.5:0.5b",
        "messages": [{"role": "user", "content": "hi"}],
    }).encode(),
    headers={"content-type": "application/json"},
)
print(json.load(urllib.request.urlopen(req)))
```

This is the same shape as the Go and curl examples — discover, then
POST to `/v1/chat/completions`. The `saturn` CLI is one way to do the
discover step; nothing about Saturn requires it.

## What just happened

```
your laptop                       same laptop
┌────────────────┐  mDNS query    ┌──────────────────────┐
│ any client:    │ ─────────────▶ │ saturn server        │
│ curl, saturnd, │                │ (advertises          │
│ saturn, fetch  │ ◀───────────── │  _saturn._tcp.local) │
└────────────────┘   TXT record   └──────────┬───────────┘
                                             │ proxies
                                             ▼
                                  ┌──────────────────────┐
                                  │ ollama (port 11434)  │
                                  └──────────────────────┘
```

Move the Saturn server to a second machine on the same LAN and every
client above will discover and use it from the first machine, unchanged.
That is the point: AI backends become a network service like printers,
not a per-app credential burden.

## Run the canned end-to-end demo

```sh
./demo/run.sh
```

`run.sh` uses the Python implementation because it is what this repo
ships and the showboat-captured walkthrough below was recorded against
it. The same six steps work with `saturnd` or a hand-rolled mDNS
client; the protocol is the contract.

## Next

- [`walkthrough.md`](walkthrough.md) — captured outputs of `run.sh`,
  with curl/Go/JS variants of each step.
- [`README.md`](README.md) — full prereqs, troubleshooting, OpenRouter
  alternative.
- `saturnd/README.md` — the Go daemon.
- `Saturn.md` (repo root) — the thesis: protocol design, ephemeral-key
  auth, OpenWRT router build.
