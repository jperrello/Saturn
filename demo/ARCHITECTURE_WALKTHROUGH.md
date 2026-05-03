# Saturn architecture walkthrough

For someone who wants to read the code. Tours the discovery flow, the
runner, the Web UI server, and traces one OpenAI-compatible
`/v1/chat/completions` request end-to-end.

For framing — what Saturn is and why — read
[`SATURN_CONTEXT.md`](../SATURN_CONTEXT.md). This doc is about the
*shape of the code*, not the pitch.

## Map of the source tree

```
saturn/
  __main__.py          CLI dispatch (saturn discover|endpoint|run|...)
  discovery.py         SaturnService dataclass, Discovery + Advertiser facades
  runner.py            Runs a service: bind port, build FastAPI, advertise
  config.py            Service TOML loader (saturn/services/*.toml)
  web.py               Web UI FastAPI server (saturn web)
  servers/
    __init__.py        OpenAI schema (ChatRequest, sse, chunk, completion)
    ollama.py          Ollama proxy with OpenAI translation
    claude.py          Anthropic proxy
    fallback.py        Cloud fallback proxy
  mdns/
    backend.py         MdnsBackend Protocol + ServiceRecord/AdvertiseSpec
    detect.py          Backend selection (bonjour/avahi/userspace)
    bonjour.py         macOS native (libdns_sd via ctypes)
    avahi.py           Linux native (avahi via dbus-python)
    userspace.py       Cross-platform fallback (python-zeroconf)
    identity.py        Stable node UUID at ~/.saturn/node_id
    settle.py          Settle-detection for one-shot discovery
    conflict.py        Name-conflict resolution
    subtypes.py        DNS-SD subtypes
  services/*.toml      Built-in service configs
```

The interesting boundary is `saturn/mdns/backend.py`: a 33-line
Protocol that any mDNS backend implements (`advertise`, `withdraw`,
`browse`, `stop_browse`, `close`). Everything above the protocol —
`SaturnDiscovery`, `SaturnAdvertiser` — is platform-agnostic.

## Discovery: `saturn discover` end-to-end

Entry point at `saturn/__main__.py:64-67`:

```python
if command in ('discover', 'endpoint'):
    sys.argv = ['saturn', command] + remaining
    from .discovery import main as discovery_main
    return discovery_main()
```

`discovery.main()` (`saturn/discovery.py:300`) is a small argparse
wrapper that calls either `cli_discover` or `cli_endpoint`. Both end
up in the public helper `discover()` (`saturn/discovery.py:185`):

```python
def discover(timeout=8.0, settle_time=1.0) -> List[SaturnService]:
    settle = SettleDetector()
    def on_change(action, service):
        if action == 'added':
            settle.arm()
    discovery = SaturnDiscovery(on_service_change=on_change)
    settle.wait(timeout=timeout)
    services = discovery.get_all_services()
    discovery.stop()
    settle.close()
    return services
```

Two pieces worth knowing:

1. **`SaturnDiscovery`** (`saturn/discovery.py:80`) — long-lived
   listener. It picks the right mDNS backend via
   `saturn.mdns.detect.backend()` (`saturn/mdns/detect.py:26`) and
   subscribes to events via `backend.browse(self._on_event)`. Each
   event carries a `ServiceRecord` (`saturn/mdns/backend.py:7`) which
   `_to_service` (`saturn/discovery.py:91`) maps onto the public
   `SaturnService` dataclass. Records are keyed by `node_id:name`
   (`saturn/discovery.py:130-133`) so the same physical node
   advertising under multiple names doesn't get dropped on conflict.

2. **`SettleDetector`** (`saturn/mdns/settle.py:4`) — wraps a
   `threading.Event` plus a one-shot timer. Each new "added" event
   re-arms a 0.5s timer; when the timer fires, the event is set and
   `discover()` returns. Cap is `timeout` (default 8s) for the case
   where nothing shows up. The single-discovery code path used to
   poll in a 15-line loop; this collapses to one wait call.

### Backend selection

`saturn/mdns/detect.py:select()`:

- macOS → `bonjour` (libdns_sd via ctypes — RFC-compliant ports).
- Linux + Avahi running → `avahi` (dbus-python).
- Windows ≥ build 17763 → native DNS-SD.
- Otherwise → `userspace` (python-zeroconf).

The `userspace` backend is also the implicit fallback if the native
backend fails to import. On macOS that fallback emits an explicit
warning (`saturn/mdns/detect.py:47-52`) because zeroconf's responses
go out from ephemeral ports, violating RFC 6762 §11. The native
backends exist specifically to fix that.

## Advertising: `saturn ollama` (or any service)

`saturn/__main__.py:97-101` resolves a bare command name against
configured services:

```python
from .config import load_service_config
if load_service_config(command):
    sys.argv = ['saturn-run', command] + remaining
    from .runner import main as runner_main
    return runner_main()
```

`saturn ollama` becomes `saturn-run ollama`. `runner.main()`
(`saturn/runner.py:550`) loads the TOML config, then `run_service()`
(`saturn/runner.py:436`) does the work:

1. **Pick a port.** `find_available_port()` (`saturn/runner.py:424`)
   binds-and-releases starting at the configured port (8080 by
   default), incrementing on `OSError`. This is also why two `saturn
   ollama` invocations on the same host get distinct ports without
   coordination.

2. **Build a FastAPI app.** Two paths:
   - **Built-in server module** (`saturn/runner.py:461-464`) — TOML
     declares `server.module = "saturn.servers.ollama"`, so we
     `importlib.import_module(...)` and grab its `app`. This is the
     Ollama path — the proxy lives in `saturn/servers/ollama.py`.
   - **Generic OpenAI proxy** (`saturn/runner.py:466-467`) —
     `ServiceRunner.create_app()` (`saturn/runner.py:328`) builds a
     FastAPI app that forwards to `config.upstream.base_url`. This
     is the OpenRouter / DeepInfra / Claude path.

3. **Advertise.** `SaturnAdvertiser` (`saturn/discovery.py:341`) gets
   instantiated with the resolved port and the service's deployment
   metadata, and `register()` (`saturn/discovery.py:423`) calls
   `backend.advertise(spec)` with a `_properties()` dict that becomes
   the TXT record:

   ```python
   props = {
       'id': get_node_id(),       # stable UUID
       'v': '2',                  # schema version
       'dep': 'local',            # deployment: local|network|cloud
       'api_type': 'ollama',
       'priority': '50',
       'features': 'network_proxy',
       'models': 'qwen2.5:0.5b,llama3.2',  # truncated to 200 bytes
       'capabilities': 'chat',
       'context': '4096',
       'cost': 'free',
   }
   ```

   `get_node_id()` (`saturn/mdns/identity.py:18`) reads
   `~/.saturn/node_id` if present and valid, otherwise generates a
   UUIDv4 and writes it. This is the v2 fix for "identity loss on
   name conflict": if the network already has an `ollama-8080`, this
   node still has the same `id`, so clients can deduplicate
   correctly.

4. **Persist run state.** `write_service_info()`
   (`saturn/runner.py:37`) writes `~/.saturn/run/<name>.json` with
   `{pid, port, mdns_name}`. `saturn stop <name>` reads this back to
   send SIGTERM. `is_service_running()` (`saturn/runner.py:68`)
   checks the same file plus a liveness probe — that's how the demo
   script knows when the proxy is up.

5. **Serve.** `uvicorn.run(app, host, actual_port)`
   (`saturn/runner.py:496`). On exit, an `atexit` cleanup
   (`saturn/runner.py:488-493`) calls `advertiser.unregister()` and
   removes the run file.

## A `/v1/chat/completions` request, traced

Setup: `saturn ollama` is running on the LAN at host `joeyair.local`
port 8080. A second laptop wants to use it.

### Step 1 — discover

The client laptop runs `saturn discover` (or any code calling
`discover()`). The flow above resolves to a `SaturnService` for
`ollama-8080` with `host="joeyair.local"`, `port=8080`,
`api_type="ollama"`, `priority=50`.

### Step 2 — pick the best one

If the caller wants automatic selection: `select_best_service()`
(`saturn/discovery.py:203`) filters by required capabilities and
context window, then sorts by `(priority, cost)` so the lowest
priority value wins, and free services beat paid at equal priority.
`get_best_service()` on the live `SaturnDiscovery` instance
(`saturn/discovery.py:174`) is the cheaper variant: just
`min(services, key=priority)`.

`saturn endpoint` is the CLI shortcut for this:
`cli_endpoint()` (`saturn/discovery.py:284`) calls `discover()` then
`min(services, key=priority).endpoint` and prints
`http://<host>:<port>`.

### Step 3 — POST the request

The client (curl, OpenAI SDK, anything) sends:

```http
POST http://joeyair.local:8080/v1/chat/completions
Content-Type: application/json

{"model": "qwen2.5:0.5b", "messages": [...], "stream": false}
```

### Step 4 — Saturn proxy receives

The Ollama proxy app from `saturn/servers/ollama.py:51` handles it:

```python
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    payload = {
        "model": request.model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "stream": request.stream,
    }
    if request.max_tokens:
        payload["options"] = {"num_predict": request.max_tokens}
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat", json=payload,
        timeout=(10, None), stream=request.stream)
```

`ChatRequest` (`saturn/servers/__init__.py:17`) is the OpenAI schema.
The translation layer here is small: rename `max_tokens` →
`options.num_predict`, otherwise pass-through.

### Step 5 — stream or buffer

For `stream=true`, the generator at `saturn/servers/ollama.py:79`
re-encodes Ollama's NDJSON into OpenAI SSE chunks via
`chunk()` (`saturn/servers/__init__.py:42`), terminating with a
`data: [DONE]` line. The wrapper `sse()`
(`saturn/servers/__init__.py:34`) returns a `StreamingResponse` with
`text/event-stream` and the `X-Accel-Buffering: no` header so
intermediaries don't buffer.

For `stream=false`, `saturn/servers/ollama.py:130-146` repackages
the response into a `completion()` envelope
(`saturn/servers/__init__.py:52`).

The cloud-proxy path (`saturn/runner.py:373-418`) is the same shape
but doesn't translate — it just adds `Authorization: Bearer
<key>` from the configured env var and proxies the bytes.

## The Web UI server

`saturn/web.py:79` instantiates a single `FastAPI` named `Saturn Web
UI`. It serves the `Web-UI/` directory as static files via the
catch-all at `saturn/web.py:1294`, plus a routes table for the
control plane:

| Route                        | Source line              | Purpose |
|------------------------------|--------------------------|---------|
| `GET /api/discover`          | `saturn/web.py:519`      | calls `discovery.discover()` in a thread executor |
| `GET /api/services`          | `saturn/web.py:402`      | list configured services + running state |
| `POST /api/services/{n}/start` | `saturn/web.py:438`    | spawn `saturn run <n>` as a subprocess |
| `POST /api/admin/auth`       | `saturn/web.py:393`      | password gate (`SATURN_ADMIN_PASSWORD` env, default `"saturn"`) |
| `POST /api/chat`             | `saturn/web.py:787`      | proxy a chat completion through the UI |
| `POST /api/system/chat`      | `saturn/web.py:873`      | tool-augmented chat for the System tab |

The interesting bit is `_resolve()` (`saturn/web.py:545`): given a
service name, it tries (1) the in-memory map of services discovered
by the most recent `/api/discover`, (2) the local run file written by
`runner.write_service_info()`, (3) the static config's `base_url`
with an Authorization header from env. That ordering is why a
LAN-discovered service preempts a configured cloud one with the same
name — a useful behavior for "I configured DeepInfra but my
neighbor is also running DeepInfra locally."

## Where to look next

- **Add a backend.** Implement `MdnsBackend` (`saturn/mdns/backend.py:28`)
  and add a branch in `saturn/mdns/detect.py:26`. Tests in
  `saturn/tests/test_*backend*.py` are the contract.
- **Add a service type.** Drop a TOML in `saturn/services/`. If it
  needs custom translation (like Ollama), add a server module
  under `saturn/servers/` and reference it from the TOML's
  `server.module`.
- **Change the TXT schema.** `_properties()`
  (`saturn/discovery.py:380`) is the writer; `_to_service()`
  (`saturn/discovery.py:91`) is the reader. The Rust router
  implementation in `saturn-router/` reads the same schema —
  changes here need to land there too.
- **Look at the Rust side.** `saturn-router/` is the OpenWRT build
  that runs on a 128 MB MIPS box. Same protocol, different
  language, different mDNS library — proves the protocol-not-SDK
  claim.

## Caveats this walkthrough doesn't cover

- Beacon advertisers (`saturn/runner.py:129, 184`) — services that
  publish a TXT record without owning a port, used to advertise
  third-party endpoints (e.g., a remote DeepInfra URL) on the LAN.
- The MCP client (`saturn/mcp_client.py`) used by the Web UI's
  System tab.
- Tunnels (`saturn/web.py:1056-1175`) — Cloudflare Quick Tunnel
  integration to expose a Saturn UI off-LAN.

For any of those, `bd ready` and `bd show <id>` will surface
in-flight work and recent decisions.
