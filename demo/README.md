# Saturn 5-minute demo

Zero-to-working chat completion against a Saturn-discovered backend on a
fresh clone. Target: under 5 minutes wall-clock on a laptop with Ollama
already installed.

## What this proves

Saturn advertises an OpenAI-compatible AI backend over mDNS/DNS-SD
(`_saturn._tcp.local.`). Any client on the LAN finds it with no
endpoint configuration and no API key. This script:

1. Starts a Saturn-advertised Ollama proxy on the local machine.
2. Discovers it via mDNS (`saturn discover`).
3. Resolves the best endpoint (`saturn endpoint`).
4. Sends an OpenAI-format `/v1/chat/completions` request.

The same flow works for any Saturn backend (OpenRouter, DeepInfra,
custom). Ollama is used here because it needs no API key.

## Prerequisites

- macOS or Linux with mDNS working on the local interface.
- Python 3.11+ and Saturn installed from this repo:
  ```sh
  pip install -e .
  ```
- [Ollama](https://ollama.com/download) installed and `ollama serve`
  running (the macOS app starts it automatically).

That's it. The script will pull a ~400 MB model on first run.

## Run it

```sh
./demo/run.sh
```

Override the model with `SATURN_DEMO_MODEL=llama3.2:1b ./demo/run.sh`.

Expected output is in [`expected-output.txt`](expected-output.txt).

## What you should see

Six numbered steps, ending in a JSON `chat.completion` response and a
green `OK — model said: ...` line. The script cleans up its background
proxy on exit (including Ctrl-C).

## Without Ollama: OpenRouter path

If you'd rather hit a hosted backend, set an OpenRouter key first and
swap the service name:

```sh
mkdir -p ~/.saturn
echo 'OPENROUTER_API_KEY=sk-or-...' >> ~/.saturn/.env
SATURN_DEMO_SERVICE=openrouter ./demo/run.sh   # not yet wired in run.sh
```

The OpenRouter path is documented for completeness; `run.sh` uses
Ollama by default to keep the demo key-free.

## Troubleshooting

- `ollama daemon not running` — start the Ollama app or run
  `ollama serve` in another terminal.
- `service did not register` — check `~/.saturn/run/ollama.json` and
  the temp log path printed by the script. Most often a port conflict
  on 8080.
- No service discovered on a corporate / guest Wi-Fi — AP isolation
  blocks mDNS. Use a home network or a wired LAN. This is a known
  limitation, see the thesis caveats.

## Files

- `run.sh` — the runnable demo (idempotent, self-cleaning).
- `expected-output.txt` — what success looks like.
- `screenshots/` — Web UI stills, populated once the Web UI is
  loadable from a packaged install.
