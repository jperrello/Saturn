# Saturn 5-minute demo

*Captured 2026-05-02T22:58:20Z by Showboat 0.6.1 against the Python
reference implementation. The protocol is language-agnostic; curl, Go
(`saturnd`), and JS variants of each step are shown alongside.*

<!-- showboat-id: 92ed5feb-c2f6-478f-9558-ebd69f7ed2d0 -->

Saturn is the DNS-SD/mDNS service type `_saturn._tcp.local.` plus a
TXT-record schema (priority, version, api, features, models). Any
language that can speak mDNS and HTTP is a peer. This walkthrough goes
from a clean install to a working OpenAI-compatible chat completion in
six commands. No API key, no endpoint configuration.

The Python `saturn` CLI is one of three equal client examples used
below. The captured outputs are from `saturn` because that is what
Showboat ran; the curl and Go (`saturnd`) blocks alongside each step
work just as well.

## 1. A Saturn implementation is installed

```bash
saturn --help | head -10
```

```output
Saturn: Zero-configuration AI service discovery

Usage: saturn <command> [options]

Commands:
  discover              Discover Saturn services on the network
    --timeout <secs>      Discovery timeout (default: 5.0)
    --json                Machine-readable JSON output
  endpoint              Output best service endpoint URL
    --timeout <secs>      Discovery timeout (default: 5.0)
```

Equivalent in other clients:

```bash
# raw protocol — needs only mDNS tooling, no Saturn install at all
dns-sd -B _saturn._tcp local.
# Go daemon
saturnd --help
```

## 2. Ollama is running locally (no Saturn service yet)

```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool | head -5
```

```output
{
    "models": [
        {
            "name": "qwen2.5:0.5b",
            "model": "qwen2.5:0.5b",
```

This step is identical for every client — Ollama is the upstream
backend, not part of Saturn. Saturn only cares that *something* on the
network speaks `/v1/chat/completions`.

## 3. Discover what is on the network — nothing yet

```bash
# curl — the protocol view, before any Saturn library
dns-sd -B _saturn._tcp local. & sleep 2; kill %1
# Go daemon
curl -sS http://localhost:7827/v1/agents
# Python reference impl (captured below)
saturn discover 2>&1 | grep -v 'Bad file' | tail -5
```

```output
Saturn: 0 services found
   └─ No local AI services on this network
   └─ Routing will use cloud fallback
```

## 4. Start a Saturn-advertised Ollama proxy

```bash
saturn stop ollama >/dev/null 2>&1 || true; saturn ollama >/tmp/saturn-demo.log 2>&1 & for i in $(seq 1 30); do [ -f ~/.saturn/run/ollama.json ] && break; sleep 0.5; done; cat ~/.saturn/run/ollama.json
```

```output
{"pid": 82305, "port": 8080, "mdns_name": "ollama-8080"}
```

This is the only step where the implementation choice shows: each
Saturn server has its own way to spin up. The wire-level effect is the
same — a process that advertises `_saturn._tcp.local.` with TXT
records and serves `/v1/*` on the advertised port. The Go saturnd
equivalent is documented in `saturnd/README.md`.

## 5. Discover again — the proxy advertises itself via mDNS

```bash
saturn discover 2>&1 | grep -v 'Bad file' | grep -v ERROR | tail -10
```

```output
2026-05-02 15:58:47,096 - INFO -   deployment: local | api_type: ollama | priority: 50
2026-05-02 15:58:47,096 - INFO -   models: none
2026-05-02 15:58:47,096 - INFO -   context: 4096 | cost: unknown
Saturn: 1 service(s) discovered
   └─ ollama-8080._saturn._tcp.local (network)
      ├─ api_type: ollama
      ├─ models: none
      ├─ capabilities: chat
      ├─ context: 4096 | cost: unknown
      └─ priority: 50
```

Same answer in other clients:

```bash
# curl — pure protocol
dns-sd -L ollama-8080 _saturn._tcp local.
# saturnd
curl -sS http://localhost:7827/v1/agents | jq '.'
```

The TXT-record fields (`api_type`, `priority`, `capabilities`, …) are
what Saturn-the-protocol actually defines. Every client decodes the
same record.

## 6. Resolve the best endpoint

```bash
saturn endpoint 2>/dev/null
```

```output
http://joeyair.local:8080
```

curl variant — Saturn protocol says "lower TXT-record `priority`
wins":

```bash
dns-sd -L ollama-8080 _saturn._tcp local. \
  | awk '/can be reached/ {print "http://" $5}'
```

saturnd variant:

```bash
curl -sS http://localhost:7827/v1/agents | jq -r '.agents | sort_by(.priority)[0].endpoint'
```

## 7. Hit it with an OpenAI-compatible request

```bash
curl -sS "$(saturn endpoint 2>/dev/null)/v1/chat/completions" -H "content-type: application/json" -d "{\"model\":\"qwen2.5:0.5b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in 5 words.\"}],\"max_tokens\":32,\"stream\":false}" | python3 -m json.tool
```

```output
{
    "id": "chatcmpl-1777762734",
    "object": "chat.completion",
    "created": 1777762734,
    "model": "qwen2.5:0.5b",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I assist you today?"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 36,
        "completion_tokens": 10,
        "total_tokens": 46
    }
}
```

JS browser variant against the same endpoint:

```js
const base = 'http://joeyair.local:8080'  // from step 6
const r = await fetch(`${base}/v1/chat/completions`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    model: 'qwen2.5:0.5b',
    messages: [{ role: 'user', content: 'Say hello in 5 words.' }],
    max_tokens: 32,
  }),
})
console.log((await r.json()).choices[0].message.content)
```

Done. mDNS browse + TXT decode + OpenAI-compatible chat completion in
seven steps, no API key, no endpoint config, no language lock-in.

```bash
saturn stop ollama
```

```output
Sent SIGTERM to ollama (PID 82305)
```
