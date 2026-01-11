# Winter Beacon Explained

This document explains the `winter_beacon.py` file chunk by chunk, covering what each part does, the types involved, and why it exists.

---

## Imports and Setup

```python
import os
import time
import socket
import argparse
import logging
import threading
import signal
import sys
import requests
from typing import Optional
from zeroconf import ServiceInfo, Zeroconf
from dotenv import load_dotenv
load_dotenv()
```

**What it does:** Loads all necessary libraries and environment variables from a `.env` file.

**Key imports:**
- `socket` - Gets hostname and IP address for mDNS registration
- `threading` - Runs the key rotation in a background thread
- `signal` - Handles graceful shutdown (Ctrl+C)
- `requests` - Makes HTTP calls to DeepInfra's API
- `zeroconf` - Python library for mDNS/DNS-SD service registration
- `Optional` from typing - Type hint indicating a value can be `None` or a specific type

**Why it exists:** The beacon needs to advertise on the network (zeroconf), call an external API (requests), run continuously (threading), and shut down cleanly (signal).

---

## Logging Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

**What it does:** Sets up logging with timestamps, module names, and log levels.

**Type:** `logger` is a `logging.Logger` instance.

**Why it exists:** Debugging and monitoring. When the beacon runs for hours, you need logs to see when keys rotated, if errors occurred, etc.

---

## JWTManager Class

```python
class JWTManager:
    def __init__(self, api_key: Optional[str] = None,
                 expires_delta: int = 600,
                 rotation_interval: int = 300):
```

**What it does:** Manages the lifecycle of scoped JWT tokens from DeepInfra.

**Types:**
- `api_key: Optional[str]` - The master DeepInfra API key (can be None, then reads from env)
- `expires_delta: int` - How long tokens live (600 seconds = 10 minutes)
- `rotation_interval: int` - How often to get new tokens (300 seconds = 5 minutes)

**Why these values:** Tokens expire in 10 minutes but we rotate every 5 minutes. This creates a safety buffer - the old token is still valid for 5 more minutes while the new one takes effect. No gaps in coverage.

### Instance Variables

```python
self.api_key = api_key or os.getenv('DEEPINFRA_API_KEY')
if not self.api_key:
    raise ValueError("DEEPINFRA_API_KEY not found in environment or constructor")

self.expires_delta = expires_delta
self.rotation_interval = rotation_interval
self.api_endpoint = "https://api.deepinfra.com/v1/scoped-jwt"

self._lock = threading.Lock()
self._current_token: Optional[str] = None
self._expires_at: Optional[float] = None
self._last_rotation: Optional[float] = None
```

**Types:**
- `self._lock: threading.Lock` - Mutex for thread safety
- `self._current_token: Optional[str]` - The JWT string, or None if not yet generated
- `self._expires_at: Optional[float]` - Unix timestamp when token expires
- `self._last_rotation: Optional[float]` - Unix timestamp of last rotation

**Why the lock:** Multiple threads access the token - the main thread reads it for mDNS registration, while the rotation thread writes new tokens. The lock prevents race conditions.

**Why underscore prefix:** Convention indicating these are "private" - other code should use the public methods instead of accessing these directly.

### generate_token Method

```python
def generate_token(self, models: Optional[list] = None, spending_limit: Optional[float] = None) -> str:
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "api_key_name": "auto",
        "expires_delta": self.expires_delta
    }

    if models is not None:
        payload["models"] = models
        if spending_limit is not None:
            payload["spending_limit"] = spending_limit

    response = requests.post(self.api_endpoint, headers=headers, json=payload)
    response.raise_for_status()

    token = response.json()["token"]

    with self._lock:
        self._current_token = token
        self._expires_at = time.time() + self.expires_delta
        self._last_rotation = time.time()

    return token
```

**What it does:** Calls DeepInfra's scoped-jwt endpoint to get a short-lived token.

**Types:**
- `models: Optional[list]` - List of model names to restrict access to (None = all models)
- `spending_limit: Optional[float]` - Max dollars to spend (not used per Adam's advice)
- Returns `str` - The JWT token

**Key behavior:**
1. Uses `"api_key_name": "auto"` - This is correct per DeepInfra docs (note: docs have a typo saying `api_token_name`)
2. Only adds `models` and `spending_limit` if provided (default: no restrictions)
3. Uses `with self._lock:` to safely update shared state
4. `raise_for_status()` throws an exception on HTTP errors (like 429 rate limit)

**Why return value:** Allows caller to use the token immediately without needing to call `get_current_token()`.

### get_current_token Method

```python
def get_current_token(self) -> Optional[str]:
    with self._lock:
        return self._current_token
```

**What it does:** Thread-safe getter for the current token.

**Type:** Returns `Optional[str]` - None if no token generated yet, otherwise the JWT string.

**Why it exists:** Other parts of the code need to read the token without risking a partial read during a write.

### needs_rotation Method

```python
def needs_rotation(self) -> bool:
    with self._lock:
        if self._last_rotation is None:
            return True

        time_since_rotation = time.time() - self._last_rotation
        return time_since_rotation >= self.rotation_interval
```

**What it does:** Checks if it's time to get a new token.

**Type:** Returns `bool`.

**Logic:**
- If never rotated (`_last_rotation is None`), definitely needs rotation
- Otherwise, compare elapsed time to the 5-minute interval

---

## BeaconAnnouncer Class

```python
class BeaconAnnouncer:
    def __init__(self, jwt_manager: JWTManager, port: int, priority: int = 10):
        self.jwt_manager = jwt_manager
        self.port = port
        self.priority = priority
        self.service_type = "_saturn._tcp.local."

        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._is_registered = False
```

**What it does:** Handles mDNS service registration using the zeroconf library.

**Types:**
- `jwt_manager: JWTManager` - The token manager instance
- `port: int` - Port number to advertise (not actually serving anything, just metadata)
- `priority: int` - Saturn priority (lower = higher priority)
- `self._zeroconf: Optional[Zeroconf]` - The zeroconf instance managing announcements
- `self._service_info: Optional[ServiceInfo]` - The service registration details

**Why `_saturn._tcp.local.`:** This is the standard Saturn service type. All Saturn services use this so clients can find them with a single browse.

### register Method

```python
def register(self) -> None:
    if self._is_registered:
        logger.warning("Service already registered. Use re-register for updates.")
        return

    token = self.jwt_manager.get_current_token()
    if not token:
        logger.warning("No current token available. Generating new token...")
        token = self.jwt_manager.generate_token()

    if len(token) > 240:
        logger.warning(
            f"ephemeral_key length ({len(token)} chars) exceeds safe limit (240 chars). "
            "mDNS TXT records have a 255-byte limit per record, and long keys may cause issues."
        )
```

**The 240-character warning:** mDNS TXT records have a 255-byte limit per key-value pair. The key name `ephemeral_key=` takes ~14 bytes, leaving ~240 for the value. JWTs can be long, so this warns if truncation might occur.

```python
    host = socket.gethostname()
    host_ip = socket.gethostbyname(host)
    service_name = f"DeepInfra-Beacon.{self.service_type}"

    self._zeroconf = Zeroconf()

    self._service_info = ServiceInfo(
        type_=self.service_type,
        name=service_name,
        port=self.port,
        addresses=[socket.inet_aton(host_ip)],
        server=f"{host}.local.",
        properties={
            'version': '1.0',
            'api': 'DeepInfra',
            'priority': str(self.priority),
            'ephemeral_key': token,
            'rotation_interval': str(self.jwt_manager.rotation_interval),
            'features': 'ephemeral_auth'
        }
    )

    self._zeroconf.register_service(self._service_info)
    self._is_registered = True
```

**What it does:** Creates and registers an mDNS service announcement.

**TXT record properties:**
- `version` - Protocol version for future compatibility
- `api` - Identifies this as a DeepInfra proxy
- `priority` - Saturn priority for service selection
- `ephemeral_key` - **The scoped JWT token** - this is the main payload
- `rotation_interval` - Tells clients how often the key changes
- `features` - Capabilities flag

**Why `socket.inet_aton(host_ip)`:** Converts IP string to bytes (required by zeroconf).

**Why `f"{host}.local."`:** mDNS convention - hostnames end in `.local.`

### unregister Method

```python
def unregister(self) -> None:
    if not self._is_registered:
        logger.warning("No service registered to unregister.")
        return

    if self._zeroconf and self._service_info:
        logger.info("Unregistering beacon service...")
        self._zeroconf.unregister_service(self._service_info)
        self._zeroconf.close()

    self._zeroconf = None
    self._service_info = None
    self._is_registered = False
```

**What it does:** Removes the service from mDNS and cleans up resources.

**Why it exists:** Clean shutdown. Without this, the service might linger in network caches for a while after the program stops.

### re_register Method

```python
def re_register(self) -> None:
    logger.info("Re-registering beacon with updated ephemeral key...")
    self.unregister()
    self.register()
    logger.info("Beacon re-registration complete.")
```

**What it does:** Unregisters then re-registers to update TXT records.

**Why this pattern:** mDNS TXT records are immutable once registered. The zeroconf library doesn't support in-place updates. The only way to change the `ephemeral_key` value is to unregister and register again.

---

## rotation_loop Function

```python
def rotation_loop(jwt_manager: JWTManager, beacon_announcer: BeaconAnnouncer) -> None:
    logger.info("Key rotation loop started")

    while True:
        try:
            if jwt_manager.needs_rotation():
                logger.info("Starting key rotation...")

                try:
                    jwt_manager.generate_token()

                    if beacon_announcer.is_registered:
                        beacon_announcer.re_register()
                    else:
                        beacon_announcer.register()

                    logger.info("Key rotation complete")
```

**What it does:** Background thread that periodically refreshes the JWT and updates the mDNS announcement.

**Pattern:** Check often (every 60 seconds), rotate less often (every 5 minutes). This allows quick startup while preventing excessive API calls.

### Error Handling

```python
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        logger.error("DeepInfra API rate limit exceeded (429). Will retry on next check (one minute).")
                    else:
                        logger.error(f"HTTP error during rotation: {e}", exc_info=True)

                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error during rotation: {e}. Will retry on next check.")

                except Exception as e:
                    logger.error(f"Unexpected error during rotation: {e}", exc_info=True)

            time.sleep(60)
```

**Why non-fatal errors:** The old token is still valid for up to 10 minutes. A single failed rotation isn't catastrophic - we'll try again in 60 seconds and still have buffer time.

**429 handling:** DeepInfra may rate-limit JWT generation. Log it specifically so operators know what's happening.

---

## main Function

```python
def main():
    parser = argparse.ArgumentParser(description='DeepInfra Beacon - mDNS JWT Announcer')
    parser.add_argument('--port', type=int, default=8090, help='Port for mDNS announcement')
    parser.add_argument('--priority', type=int, default=10, help='Beacon priority (lower is higher priority)')
    args = parser.parse_args()

    if not os.getenv('DEEPINFRA_API_KEY'):
        logger.error("DEEPINFRA_API_KEY environment variable not set")
        sys.exit(1)
```

**What it does:** Parses CLI arguments and validates environment.

**CLI args:**
- `--port` - The port number to advertise (default 8090)
- `--priority` - Saturn priority level (default 10)

**Note:** The port doesn't mean the beacon serves HTTP on that port. It's just metadata for the TXT record.

### Signal Handling

```python
    def shutdown_beacon(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        beacon_announcer.unregister()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_beacon)
    signal.signal(signal.SIGTERM, shutdown_beacon)
```

**What it does:** Catches Ctrl+C (SIGINT) and kill signals (SIGTERM) to unregister cleanly.

**Why it exists:** Without this, the mDNS announcement might persist after shutdown, causing clients to try connecting to a dead service.

### Startup Sequence

```python
    logger.info("Generating initial JWT...")
    token = jwt_manager.generate_token()
    logger.info(f"✓ Generated JWT (len={len(token)} chars, expires in {jwt_manager.expires_delta}s)")

    logger.info("Registering beacon on mDNS network...")
    beacon_announcer.register()
    logger.info(f"✓ Beacon registered on port {args.port} with priority {args.priority}")

    rotation_thread = threading.Thread(
        target=rotation_loop,
        args=(jwt_manager, beacon_announcer),
        daemon=True,
        name="KeyRotationThread"
    )
    rotation_thread.start()
```

**Startup order:**
1. Generate initial token (so we have something to announce)
2. Register the mDNS service
3. Start the background rotation thread

**Why `daemon=True`:** Daemon threads die when the main thread exits. Without this, the program would hang on shutdown waiting for the rotation thread.

### Main Loop

```python
    try:
        signal.pause()
    except AttributeError:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        beacon_announcer.unregister()
```

**What it does:** Keeps the main thread alive while the daemon thread does the work.

**Why `signal.pause()` with fallback:** `signal.pause()` is Unix-only. On Windows, it doesn't exist (`AttributeError`), so we fall back to a simple sleep loop.

---

## How It Works When You Run It

```
$ python beacons/winter_beacon.py --port 8090 --priority 5
```

1. **Environment check** - Fails immediately if `DEEPINFRA_API_KEY` not set
2. **Initial token generation** - Calls DeepInfra API, gets a JWT valid for 10 minutes
3. **mDNS registration** - Announces `DeepInfra-Beacon._saturn._tcp.local.` with the JWT in TXT records
4. **Background rotation** - Thread wakes every 60 seconds, regenerates token every 5 minutes
5. **Re-registration** - Each rotation triggers unregister → register to update the `ephemeral_key`
6. **Idle** - Main thread waits for Ctrl+C
7. **Shutdown** - Unregisters from mDNS, exits cleanly

---

## Comparison to servers/ Directory

| Aspect | winter_beacon.py | servers/*.py |
|--------|------------------|--------------|
| **Purpose** | Announces credentials | Proxies requests |
| **Serves HTTP** | No | Yes (FastAPI) |
| **mDNS Role** | Pure announcement | Announcement + actual service |
| **Port Usage** | Metadata only | Actually binds to port |
| **TXT Records** | Contains `ephemeral_key` | Contains `version`, `api`, `priority` |
| **Continuous** | Runs forever, rotates keys | Runs forever, handles requests |

**Key difference:** The beacon doesn't serve any HTTP traffic. It only exists to put a short-lived API key on the network via mDNS. Clients discover the beacon, extract the `ephemeral_key` from TXT records, then use that key to talk to DeepInfra's cloud API directly (or through another Saturn server).

---

## Does It Accomplish the Goals?

| Goal | Status | Notes |
|------|--------|-------|
| Locally announces how to access service beyond LAN | ✅ | Announces `ephemeral_key` via mDNS TXT records |
| Uses DeepInfra scoped JWT | ✅ | Calls `https://api.deepinfra.com/v1/scoped-jwt` |
| Key expires in few minutes | ✅ | Default 10-minute expiry, 5-minute rotation |
| Keeps key updated | ✅ | Background thread rotates every 5 minutes |
| Uses correct parameter name | ✅ | Uses `api_key_name` (not the typo `api_token_name`) |
| Skips spending_limit | ✅ | Only uses `expires_delta` per Adam's advice |
| Handles mDNS length limit | ✅ | Warns if token > 240 chars |
| Defaults to all models | ✅ | `models` parameter not sent, defaults to all |

**The beacon fully accomplishes all stated goals.**

---

## What Clients Need to Do

To use the beacon, a client must:

1. Browse for `_saturn._tcp.local.` services
2. Find service with `api: DeepInfra` and `features: ephemeral_auth` in TXT records
3. Extract the `ephemeral_key` value
4. Use that key as `Authorization: Bearer {ephemeral_key}` when calling DeepInfra API
5. Re-discover periodically (at least every `rotation_interval` seconds) to get fresh keys

The beacon is a credential distribution mechanism, not a proxy. It solves the problem of sharing API access without sharing the master key.
