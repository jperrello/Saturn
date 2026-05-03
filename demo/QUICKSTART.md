# Saturn Quickstart

Saturn advertises OpenAI-compatible AI backends over mDNS. Clients on
the same LAN find them with no API key and no endpoint configuration.
This page gets you a working chat completion in under 5 minutes.

## You need

- macOS or Linux on a network where mDNS works (home Wi-Fi or wired —
  not eduroam / corporate guest Wi-Fi, which block mDNS).
- Python 3.11+.
- [Ollama](https://ollama.com/download) installed and running. The
  macOS app starts the daemon for you; on Linux run `ollama serve`.

No API key. No account. No subscription.

## Install Saturn

```sh
git clone https://github.com/jperrello/Saturn.git
cd Saturn
pip install -e .
```

## Run the demo

```sh
./demo/run.sh
```

That's it. The script:

1. Checks `saturn` and `ollama` are present.
2. Pulls `qwen2.5:0.5b` (~400 MB) the first time.
3. Starts a Saturn-advertised Ollama proxy in the background.
4. Calls `saturn discover` — finds the proxy via mDNS.
5. Calls `saturn endpoint` — resolves the best service URL.
6. Sends an OpenAI-format `/v1/chat/completions` request and prints
   the response.

It cleans up its background proxy on exit (including Ctrl-C).

Expected output is in [`expected-output.txt`](expected-output.txt). A
step-by-step walkthrough with captured outputs is in
[`walkthrough.md`](walkthrough.md). Full prereqs, troubleshooting, and
the OpenRouter (hosted) alternative are in [`README.md`](README.md).

## What just happened

```
your laptop                       same laptop
┌────────────────┐  mDNS query    ┌──────────────────────┐
│ saturn         │ ─────────────▶ │ saturn ollama        │
│ discover       │                │ (advertises          │
│                │ ◀───────────── │  _saturn._tcp.local) │
└────────────────┘   TXT record   └──────────┬───────────┘
                                             │ proxies
                                             ▼
                                  ┌──────────────────────┐
                                  │ ollama (port 11434)  │
                                  └──────────────────────┘
```

Move `saturn ollama` to a second machine on the same LAN and the same
`./demo/run.sh` from your laptop will discover and use it. That is the
whole point: AI backends become a network service like printers, not a
per-app credential burden.

## Use it from your own code

```python
import os, urllib.request, json, subprocess

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

Same idea works with the OpenAI Python SDK by setting `base_url=base`
and any non-empty `api_key`.

## Next

- `saturn --help` — full CLI surface.
- `saturn config list` — see all configured backends (Ollama,
  OpenRouter, DeepInfra, Claude, custom).
- `saturn config new` — register your own backend.
- The thesis (`Saturn.md` in the repo) explains the protocol design,
  the ephemeral-key auth model, and the OpenWRT router build.
