# Saturn 5-minute demo

*2026-05-02T22:58:20Z by Showboat 0.6.1*
<!-- showboat-id: 92ed5feb-c2f6-478f-9558-ebd69f7ed2d0 -->

Saturn is zero-config service discovery for OpenAI-compatible AI backends on a LAN. This walkthrough goes from a clean Saturn install to a working chat completion in six commands. No API key, no endpoint configuration.

## 1. Saturn is installed

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

## 3. Discover what is on the network — nothing yet

```bash
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
{"pid": 82305, "port": 8080, "mdns_name": "ollama-8080"}```
```

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

## 6. Resolve the best endpoint

```bash
saturn endpoint 2>/dev/null
```

```output
http://joeyair.local:8080
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

Done. mDNS discovery + OpenAI-compatible chat completion in seven steps, no API key, no endpoint config.

```bash
saturn stop ollama
```

```output
Sent SIGTERM to ollama (PID 82305)
```
