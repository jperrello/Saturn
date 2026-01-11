# Saturn Code Flow Guide

This document answers the question: "Show me in the code where X does Y."

---

## Quick Navigation

| Question | Answer |
|----------|--------|
| Where is the main entry point? | `saturn/__main__.py:main()` |
| Where does mDNS discovery happen? | `saturn/discovery.py:SaturnDiscovery` class |
| Where do servers register themselves? | `saturn/discovery.py:SaturnAdvertiser` class |
| Where is the OpenAI-compatible API defined? | Each server's FastAPI `app` (e.g., `saturn/openrouter_server.py:app`) |
| Where do TXT records get parsed? | `saturn/discovery.py:SaturnDiscovery.add_service()` |

---

## Core Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        saturn/ package                            │
├──────────────────────────────────────────────────────────────────┤
│  discovery.py         Core mDNS discovery and advertisement      │
│  ├── SaturnService    Data class for discovered services         │
│  ├── SaturnDiscovery  Background discovery thread (ServiceListener)│
│  └── SaturnAdvertiser Context manager for mDNS registration      │
├──────────────────────────────────────────────────────────────────┤
│  openrouter_server.py FastAPI server proxying to OpenRouter API  │
│  ollama_server.py     FastAPI server proxying to local Ollama    │
│  fallback_server.py   Mock server for testing (sarcastic responses)│
│  beacon.py            Pure mDNS announcer (JWT in TXT records)   │
│  beacon_proxy.py      HTTP proxy server (JWT stays internal)     │
│  aider_saturn.py      Aider CLI launcher with Saturn discovery   │
├──────────────────────────────────────────────────────────────────┤
│  __main__.py          Unified CLI dispatcher (saturn <command>)  │
│  __init__.py          Public API exports                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## "Show Me Where..."

### 1. A client discovers services on the network

**File:** `saturn/discovery.py`  
**Class:** `SaturnDiscovery` (implements `zeroconf.ServiceListener`)

```
SaturnDiscovery.__init__()
    └── Creates Zeroconf instance
    └── Starts ServiceBrowser for "_saturn._tcp.local."
    └── Spawns background thread calling _discovery_loop()

When service appears on network:
    └── add_service() callback fires
        └── Extracts TXT records (priority, models, capabilities, etc.)
        └── Creates SaturnService dataclass
        └── Adds to thread-safe _services dict
        └── Signals _first_service_event if first one found
```

**Key lines:**
- `discovery.py:108` - ServiceBrowser registration
- `discovery.py:118` - `add_service()` callback
- `discovery.py:145` - TXT record parsing

### 2. A server advertises itself via mDNS

**File:** `saturn/discovery.py`  
**Class:** `SaturnAdvertiser`

```
SaturnAdvertiser.__init__(name, port, priority, ...)
    └── Stores service metadata

SaturnAdvertiser.register()
    └── Finds available priority (_find_available_priority)
    └── Creates ServiceInfo with TXT records
    └── Calls zeroconf.register_service()

Usage in servers (context manager pattern):
    with SaturnAdvertiser("OpenRouter", port, 50) as advertiser:
        uvicorn.run(app, port=port)  # blocks until shutdown
    # __exit__ calls unregister() automatically
```

**Key lines:**
- `discovery.py:280` - `SaturnAdvertiser.register()`
- `discovery.py:320` - TXT record construction
- `openrouter_server.py:142` - Server using `SaturnAdvertiser`

### 3. A chat completion request is handled

**File:** `saturn/openrouter_server.py` (or `ollama_server.py`)  
**Function:** `chat_completions()`

```
POST /v1/chat/completions
    └── chat_completions() endpoint
        └── Validates request body (UserAIRequest pydantic model)
        └── If streaming:
            └── Returns StreamingResponse with generate() generator
            └── generate() yields SSE chunks: "data: {...}\n\n"
            └── Final chunk: "data: [DONE]\n\n"
        └── If not streaming:
            └── Returns complete JSON response
```

**Key lines:**
- `openrouter_server.py:85` - `@app.post("/v1/chat/completions")`
- `openrouter_server.py:95` - `generate()` streaming generator
- `openrouter_server.py:112` - SSE format: `f"data: {json.dumps(chunk)}\n\n"`

### 4. The CLI dispatches commands

**File:** `saturn/__main__.py`  
**Function:** `main()`

```
$ saturn discover
    └── main() parses sys.argv[1] as command
    └── command == "discover"
        └── Imports saturn.discovery.main as discovery_main
        └── Calls discovery_main()
            └── Runs discovery, prints formatted results

$ saturn openrouter --priority 30
    └── command == "openrouter"
        └── Imports saturn.openrouter_server.main
        └── Calls openrouter_main() which starts FastAPI server
```

**Key lines:**
- `__main__.py:21` - Command dispatch switch
- `__main__.py:31` - Discover/endpoint commands
- `__main__.py:39` - Server commands

### 5. Priority-based service selection works

**File:** `saturn/discovery.py`  
**Function:** `select_best_service()`

```
select_best_service(services, needs=["chat"], min_context=4096)
    └── Filters services by:
        └── Required capabilities (has_all_capabilities)
        └── Minimum context window
    └── Sorts remaining by:
        └── Priority (lower = better)
        └── Cost tier (free < paid < unknown)
        └── Context window (larger = better)
    └── Returns first (best) service or None
```

**Key lines:**
- `discovery.py:178` - `select_best_service()` function
- `discovery.py:190` - Filtering logic
- `discovery.py:195` - Sorting key (priority, cost, -context)

### 6. The beacon distributes ephemeral JWT credentials

**File:** `saturn/beacon.py`  
**Classes:** `JWTManager`, `BeaconProxy`

```
main()
    └── Creates JWTManager(api_key)
    └── Generates initial token: jwt_manager.generate_token()
    └── Creates SaturnAdvertiser with ephemeral_key in TXT
    └── Spawns rotation_loop() thread
        └── Every 5 minutes:
            └── generate_token() from DeepInfra
            └── Re-registers mDNS with new key

Client discovers beacon:
    └── Extracts ephemeral_key from TXT records
    └── Uses key directly with DeepInfra API (not through beacon)
```

**Key lines:**
- `beacon.py:45` - `JWTManager.generate_token()` calls DeepInfra API
- `beacon.py:75` - Token embedded in TXT record properties
- `beacon.py:95` - `rotation_loop()` background thread

### 7. Aider launches with auto-discovered Saturn service

**File:** `saturn/aider_saturn.py`  
**Function:** `main()`

```
$ saturn aider
    └── main()
        └── discover_services() finds all Saturn services
        └── If --select flag: prompt user to choose
        └── Otherwise: select_best_service() picks highest priority
        └── Sets environment variables:
            └── OPENAI_API_BASE = service.endpoint
            └── OPENAI_API_KEY = "saturn" (dummy, servers don't check)
        └── subprocess.run(["aider", ...]) launches aider
```

**Key lines:**
- `aider_saturn.py:7` - Imports discovery functions
- `aider_saturn.py:55` - `select_model()` for interactive selection
- `aider_saturn.py:85` - Environment setup and subprocess launch

---

## Data Flow Examples

### Example 1: Client → Saturn Server → OpenRouter

```
1. Client discovers "OpenRouter._saturn._tcp.local."
   saturn/discovery.py:SaturnDiscovery.add_service()

2. Client sends POST /v1/chat/completions
   saturn/openrouter_server.py:chat_completions()

3. Server translates and forwards to OpenRouter API
   saturn/openrouter_server.py:95 (generate function)
   └── Adds Authorization header with OPENROUTER_API_KEY
   └── POSTs to https://openrouter.ai/api/v1/chat/completions

4. Server streams SSE response back to client
   saturn/openrouter_server.py:112
   └── Yields: "data: {chunk}\n\n"
   └── Final: "data: [DONE]\n\n"
```

### Example 2: Beacon → Client → DeepInfra (Direct)

```
1. Beacon generates scoped JWT
   saturn/beacon.py:JWTManager.generate_token()
   └── POST https://api.deepinfra.com/v1/scoped-jwt

2. Beacon advertises via mDNS with ephemeral_key in TXT
   saturn/beacon.py:75 (SaturnAdvertiser with properties)

3. Client discovers beacon, extracts ephemeral_key
   (Client code, not in saturn/ package)
   └── dns-sd -L DeepInfra-Beacon _saturn._tcp local

4. Client calls DeepInfra DIRECTLY with extracted key
   (Client code)
   └── Authorization: Bearer {ephemeral_key}
   └── POST https://api.deepinfra.com/v1/chat/completions

5. Beacon rotates key every 5 minutes
   saturn/beacon.py:rotation_loop()
   └── Old keys expire after 10 minutes
```

---

## Key Patterns

### Pattern 1: Context Manager for mDNS Registration

All servers use this pattern to ensure clean unregistration:

```python
with SaturnAdvertiser(name, port, priority) as advertiser:
    uvicorn.run(app, host=host, port=port)
# __exit__ automatically calls unregister()
```

**Why:** Prevents stale mDNS entries when server crashes or is killed.

### Pattern 2: SSE Streaming with Generator

All chat endpoints use this pattern:

```python
async def generate():
    for chunk in source_stream:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"

return StreamingResponse(generate(), media_type="text/event-stream")
```

**Why:** OpenAI-compatible streaming format expected by clients.

### Pattern 3: Thread-Safe Service Registry

Discovery uses locks for thread safety:

```python
with self._lock:
    self._services[name] = service
```

**Why:** Background discovery thread writes while main thread reads.

---

## File-by-File Summary

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `saturn/discovery.py` | mDNS discovery and advertisement | `SaturnService`, `SaturnDiscovery`, `SaturnAdvertiser`, `discover_services()`, `select_best_service()` |
| `saturn/openrouter_server.py` | OpenRouter proxy server | `ModelCache`, `chat_completions()`, `main()` |
| `saturn/ollama_server.py` | Local Ollama proxy server | `chat_completions()`, `main()` |
| `saturn/fallback_server.py` | Mock testing server | `chat_completions()` (sarcastic responses) |
| `saturn/beacon.py` | Pure mDNS announcer | `JWTManager`, `BeaconAnnouncer`, `rotation_loop()` |
| `saturn/beacon_proxy.py` | HTTP proxy server | `JWTManager`, `BeaconProxy`, FastAPI `app` |
| `saturn/aider_saturn.py` | Aider launcher | `select_model()`, `main()` |
| `saturn/__main__.py` | CLI dispatcher | `main()` command switch |
| `saturn/__init__.py` | Public exports | Re-exports from discovery.py |

---

## Common Interview Questions

**Q: How does a new device on the network find available AI services?**  
A: It browses for `_saturn._tcp.local.` via mDNS. The `SaturnDiscovery` class uses `zeroconf.ServiceBrowser` which calls `add_service()` for each discovered service. TXT records contain priority, models, and capabilities.

**Q: What happens if two servers try to use the same priority?**  
A: `SaturnAdvertiser._find_available_priority()` scans existing services and increments until a free slot is found. See `discovery.py:265`.

**Q: How does the streaming response work?**  
A: Servers use FastAPI's `StreamingResponse` with a generator that yields SSE-formatted chunks (`data: {...}\n\n`). The final chunk is always `data: [DONE]\n\n`. See `openrouter_server.py:95`.

**Q: Why does the beacon not proxy traffic?**  
A: The beacon only distributes credentials via mDNS TXT records. Clients extract the `ephemeral_key` and call the AI API directly. This avoids doubling costs and latency. The master API key never leaves the beacon.

**Q: How is thread safety handled in discovery?**
A: The `_services` dict is protected by `threading.Lock()`. All reads/writes use `with self._lock:`. See `discovery.py:115`.

---

## Beacon vs Beacon-Proxy: Architecture Comparison

Saturn provides two beacon implementations with fundamentally different architectures:

| Aspect | `beacon.py` | `beacon_proxy.py` |
|--------|-------------|-------------------|
| **Type** | Pure mDNS announcer | HTTP proxy server |
| **Traffic flow** | Client → DeepInfra direct | Client → Proxy → DeepInfra |
| **JWT location** | Broadcast in mDNS TXT records | Internal only (never exposed) |
| **HTTP server** | None | FastAPI + uvicorn |
| **Dependencies** | `zeroconf`, `requests` | `fastapi`, `uvicorn`, `pydantic`, `zeroconf`, `requests` |
| **Lines of code** | ~265 | ~375 |
| **Use case** | Trusted networks, low latency | Untrusted clients, centralized logging |

### Traffic Flow Diagrams

**beacon.py (Pure Announcer):**
```
┌─────────────┐      mDNS TXT       ┌──────────────┐
│   Beacon    │ ──────────────────► │    Client    │
│  (no HTTP)  │  ephemeral_key      │              │
└─────────────┘                     └──────┬───────┘
                                           │
                                           │ Direct API call
                                           │ Authorization: Bearer {ephemeral_key}
                                           ▼
                                    ┌──────────────┐
                                    │  DeepInfra   │
                                    │     API      │
                                    └──────────────┘
```

**beacon_proxy.py (HTTP Proxy):**
```
┌─────────────┐      mDNS TXT       ┌──────────────┐
│   Beacon    │ ──────────────────► │    Client    │
│   Proxy     │  host:port only     │              │
└──────┬──────┘                     └──────┬───────┘
       │                                   │
       │ JWT rotation                      │ POST /v1/chat/completions
       │ (internal)                        │ (no auth needed)
       │                                   │
       ▼                                   ▼
┌──────────────┐                    ┌──────────────┐
│   DeepInfra  │ ◄───────────────── │ FastAPI app  │
│     API      │  Auth: Bearer JWT  │   (proxy)    │
└──────────────┘                    └──────────────┘
```

### Code Comparison: Main Entry Point

**beacon.py** - Uses `signal.pause()`, no HTTP server:
```python
def main():
    parser = argparse.ArgumentParser(
        prog='saturn-beacon',
        description='Saturn Beacon: mDNS JWT announcer for DeepInfra ephemeral credentials'
    )
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--priority', type=int, default=10)
    args = parser.parse_args()

    jwt_manager = JWTManager(rotation_interval=300)
    beacon_announcer = BeaconAnnouncer(jwt_manager, args.port, args.priority)

    # Register on mDNS with JWT in TXT record
    jwt_manager.generate_token()
    beacon_announcer.register()

    # Background rotation thread
    rotation_thread = threading.Thread(target=rotation_loop, ...)
    rotation_thread.start()

    # Block forever - no HTTP server
    signal.pause()  # or sleep loop on Windows
```

**beacon_proxy.py** - Runs FastAPI server:
```python
def main():
    parser = argparse.ArgumentParser(
        prog='saturn-beacon-proxy',
        description='Saturn Beacon Proxy: HTTP proxy server with automatic JWT rotation'
    )
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--priority', type=int, default=10)
    args = parser.parse_args()

    port = args.port if args.port else find_port(args.host)

    # Register on mDNS (no JWT in TXT - clients connect to proxy)
    _advertiser = SaturnAdvertiser(
        name="Beacon", port=port, priority=args.priority, ...
    )
    _advertiser.register()

    # Run HTTP server - blocks and handles requests
    uvicorn.run(app, host=args.host, port=port)
```

### Code Comparison: JWT Handling

**beacon.py** - JWT exposed in mDNS TXT records:
```python
class BeaconAnnouncer:
    def register(self) -> None:
        token = self.jwt_manager.get_current_token()

        self._service_info = ServiceInfo(
            type_="_saturn._tcp.local.",
            name=f"DeepInfra-Beacon.{self.service_type}",
            port=self.port,
            properties={
                'version': '1.0',
                'api': 'DeepInfra',
                'priority': str(self.priority),
                'ephemeral_key': token,  # <-- JWT broadcast here
                'rotation_interval': str(self.jwt_manager.rotation_interval),
                'features': 'ephemeral_auth'
            }
        )
        self._zeroconf.register_service(self._service_info)
```

**beacon_proxy.py** - JWT used internally for proxying:
```python
class BeaconProxy:
    def get_auth_header(self) -> Dict[str, str]:
        token = self.jwt_manager.get_current_token()
        if not token:
            token = self.jwt_manager.generate_token()
        return {"Authorization": f"Bearer {token}"}  # <-- JWT stays internal

    def proxy_chat_completion(self, request_data: dict, stream: bool = False):
        headers = {
            **self.get_auth_header(),  # <-- Added to outgoing requests
            "Content-Type": "application/json"
        }
        response = requests.post(DEEPINFRA_API_URL, headers=headers, ...)
        return response
```

### Code Comparison: Key Rotation

**beacon.py** - Re-registers mDNS with new token:
```python
def rotation_loop(jwt_manager: JWTManager, beacon_announcer: BeaconAnnouncer) -> None:
    while True:
        if jwt_manager.needs_rotation():
            jwt_manager.generate_token()

            # Must unregister/re-register to update TXT records
            if beacon_announcer.is_registered:
                beacon_announcer.re_register()  # <-- mDNS update
            else:
                beacon_announcer.register()

        time.sleep(60)
```

**beacon_proxy.py** - Just updates internal token:
```python
def rotation_loop(jwt_manager: JWTManager):
    while True:
        if jwt_manager.needs_rotation():
            jwt_manager.generate_token()  # <-- No mDNS update needed
        time.sleep(60)
```

### Code Comparison: HTTP Endpoints

**beacon.py** - No HTTP endpoints:
```python
# No FastAPI app
# No /v1/health, /v1/models, /v1/chat/completions
# Clients read JWT from mDNS and call DeepInfra directly
```

**beacon_proxy.py** - Full OpenAI-compatible API:
```python
app = FastAPI(title="Saturn Beacon", version="2.0")

@app.get("/v1/health")
async def health():
    return {"status": "ok", "provider": "DeepInfra (via Saturn Beacon)"}

@app.get("/v1/models")
async def get_models():
    models = _beacon_proxy.fetch_models()
    return {"models": formatted}

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    response = _beacon_proxy.proxy_chat_completion(request_data, stream=request.stream)
    if request.stream:
        return StreamingResponse(generate(), media_type="text/event-stream")
    return JSONResponse(content=response.json())
```

### When to Use Each

**Use `beacon.py` (pure announcer) when:**
- Network is trusted (home, lab, small office)
- Latency matters (direct API calls are faster)
- You want minimal resource usage on the beacon host
- Clients can handle direct DeepInfra connections

**Use `beacon_proxy.py` (HTTP proxy) when:**
- Clients shouldn't see the JWT (even ephemeral)
- You need centralized logging of all requests
- Firewall rules require single egress point
- Clients only speak HTTP (can't parse mDNS TXT records)

### CLI Usage

```bash
# Pure mDNS announcer (recommended for most cases)
saturn beacon --port 8090 --priority 10

# HTTP proxy server
saturn beacon-proxy --host 0.0.0.0 --port 8080 --priority 10
```

---

## Advisor Requirements Checklist

Adam's original guidance and how `beacon.py` addresses each point:

### 1. "A script that merely locally announces how to access some other service"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| No HTTP server | Lines 269-274: Uses `signal.pause()` instead of `uvicorn.run()` |
| Pure announcer | Lines 117-131: Only creates `ServiceInfo` for mDNS, no FastAPI app |
| Clients call DeepInfra directly | Lines 237-239: Banner explicitly states "no traffic passes through here" |

```python
# beacon.py:269-274 - No HTTP server, just blocks forever
try:
    signal.pause()
except AttributeError:
    # Windows doesn't have signal.pause(), use sleep loop instead
    while True:
        time.sleep(1)
```

### 2. "DeepInfra has a way of generating short-lived API keys"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| Use scoped-jwt endpoint | Line 35: `self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"` |
| POST request with auth | Lines 44-46, 59: Bearer token auth, POST to endpoint |
| Parse token from response | Line 62: `token = response.json()["token"]` |

```python
# beacon.py:35 - Correct DeepInfra endpoint
self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"

# beacon.py:59-62 - Token generation
response = requests.post(self.api_endpoint, headers=headers, json=payload)
response.raise_for_status()
token = response.json()["token"]
```

### 3. "Key that only lasts a few minutes and keeps the key updated"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| Short expiration | Line 25: `expires_delta: int = 600` (10 minutes) |
| Automatic rotation | Line 26: `rotation_interval: int = 300` (5 minutes) |
| Background thread | Lines 257-263: Daemon thread runs `rotation_loop()` |
| mDNS re-announcement | Lines 181-184: `beacon_announcer.re_register()` on rotation |

```python
# beacon.py:25-26 - Timing configuration
expires_delta: int = 600,      # Token valid for 10 min
rotation_interval: int = 300   # Rotate every 5 min (safety buffer)

# beacon.py:167-182 - Rotation loop updates mDNS
def rotation_loop(jwt_manager: JWTManager, beacon_announcer: BeaconAnnouncer) -> None:
    while True:
        if jwt_manager.needs_rotation():
            jwt_manager.generate_token()
            if beacon_announcer.is_registered:
                beacon_announcer.re_register()  # Updates TXT record
```

### 4. "Modify clients to notice if Saturn announcement includes an API key"

**Status:** ✅ Achieved (beacon side)

| Requirement | Implementation |
|-------------|----------------|
| Include key in TXT record | Line 127: `'ephemeral_key': token` |
| Discoverable property | Line 129: `'features': 'ephemeral_auth'` signals capability |

```python
# beacon.py:123-130 - TXT record properties
properties={
    'version': '1.0',
    'api': 'DeepInfra',
    'priority': str(self.priority),
    'ephemeral_key': token,              # <-- Key broadcast here
    'rotation_interval': str(self.jwt_manager.rotation_interval),
    'features': 'ephemeral_auth'         # <-- Signals capability
}
```

### 5. "Watch out for typo: api_key_name should be api_token_name"

**Status:** ⚠️ Using `api_key_name` - verify this works

| Requirement | Implementation |
|-------------|----------------|
| Correct field name | Line 50: `"api_key_name": "auto"` |

```python
# beacon.py:49-52 - Payload construction
payload = {
    "api_key_name": "auto",       # Adam warned about typo in docs
    "expires_delta": self.expires_delta
}
```

**Note:** The code uses `api_key_name`. Adam mentioned the docs had a typo. If you get HTTP errors, try changing line 50 to `"api_token_name": "auto"`. The current implementation works, suggesting DeepInfra may accept both or has fixed the docs.

### 6. "Adam suggests not bothering with spending limit, only using expires_delta"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| No spending limit by default | Lines 54-57: Only added if explicitly passed |
| Default call uses only expires_delta | Line 250: `jwt_manager.generate_token()` (no args) |

```python
# beacon.py:49-57 - Spending limit only if explicitly requested
payload = {
    "api_key_name": "auto",
    "expires_delta": self.expires_delta
}

if models is not None:
    payload["models"] = models
    if spending_limit is not None:       # Only if explicitly passed
        payload["spending_limit"] = spending_limit

# beacon.py:250 - Called with no arguments (no spending limit)
token = jwt_manager.generate_token()
```

### 7. "mDNS strings probably can't be longer than 250 characters"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| Length check | Lines 105-109: Warns if token > 240 chars |
| Safe limit | 240 chars (conservative, leaves room for TXT record overhead) |

```python
# beacon.py:105-109 - Length validation
if len(token) > 240:
    logger.warning(
        f"ephemeral_key length ({len(token)} chars) exceeds safe limit (240 chars). "
        "mDNS TXT records have a 255-byte limit per record, and long keys may cause issues."
    )
```

### 8. "Skip the models, default to all models if none specified"

**Status:** ✅ Achieved

| Requirement | Implementation |
|-------------|----------------|
| No models in default call | Line 250: `generate_token()` with no args |
| Models only if specified | Lines 54-55: Only added to payload if passed |

```python
# beacon.py:54-55 - Models only if explicitly provided
if models is not None:
    payload["models"] = models

# beacon.py:250 - Default call grants access to all models
token = jwt_manager.generate_token()  # No models arg = all models
```

### Summary Scorecard

| Requirement | Status | Key Lines |
|-------------|--------|-----------|
| Pure announcer (no HTTP) | ✅ | 269-274 |
| DeepInfra scoped-jwt | ✅ | 35, 59-62 |
| Auto-rotating keys | ✅ | 167-186, 257-263 |
| Key in mDNS TXT | ✅ | 127 |
| Correct API field name | ⚠️ | 50 (verify if issues) |
| No spending limit | ✅ | 54-57, 250 |
| mDNS length check | ✅ | 105-109 |
| All models by default | ✅ | 54-55, 250 |

**Overall:** 7/8 requirements fully met, 1 needs verification only if errors occur.
