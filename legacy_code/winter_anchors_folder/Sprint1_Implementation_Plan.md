# Winter Sprint 1 Implementation Plan

Research Summary: DeepInfra Scoped JWTs

API Endpoint: POST [**https://api.deepinfra.com/v1/scoped-jwt**](https://api.deepinfra.com/v1/scoped-jwt)

Request:

```
  {
    "api_key_name": "auto",
    "models": ["model-id"],  // OMIT for all models (Adam's requirement)
    "expires_delta": 3600,     // Seconds until expiration
    "spending_limit": 1.0     // SKIP for now (Adam's requirement)
  }
```

Response: {"token": "jwt:eyJhbGci..."}

Key Constraints:  
\- Requires Authorization header with main API key to mint tokens  
\- exp field cannot exceed one week from issuance  
\- Tokens are standard JWTs with jwt: prefix  
\- Can be used like regular API keys in inference calls

\---  
Architecture Decision: Zeroconf Library

Using Python zeroconf library instead of dns-sd subprocess because:

**1\. Dynamic TXT Updates (The Killer Argument):** Key rotation requires updating TXT records every few minutes. With zeroconf, we call `unregister_service()` then `register_service()` with new properties \- clean, atomic, programmatic. With dns-sd subprocess, we'd have to:

- Kill the running dns-sd process  
- Parse stdout/stderr to confirm termination  
- Spawn a new process with new parameters  
- Handle race conditions if the old process doesn't die cleanly This is fragile and adds failure modes (zombie processes, port conflicts, timing bugs).

**2\. Native Python Data Structures:** Zeroconf provides direct property dictionary access. Clients read: `info.properties.get(b'ephemeral_key').decode('utf-8')`

With dns-sd subprocess, we'd parse text output like: `ephemeral_key=jwt:eyJ...` from stdout, handling encoding issues, parsing edge cases, and potential format changes across dns-sd versions.

**3\. Cross-Platform Portability:** Pure Python implementation works on macOS, Linux, and Windows without requiring the dns-sd binary (which is part of Bonjour/mDNSResponder). Saturn beacons could run anywhere \- Docker containers, cloud VMs, Raspberry Pis \- without ensuring dns-sd is installed. This matters because Saturn users could be writing clients in ANY language, but the beacon server is Python.

**4\. Error Handling & Exceptions:** Native libraries raise proper Python exceptions (NonUniqueNameException, ServiceNotFound, etc.). Subprocess failures return opaque exit codes and stderr text that must be parsed. Exceptions bubble up naturally through the call stack; subprocess errors require explicit handling at every call site.

**5\. Async Compatibility:** Zeroconf supports asyncio under the hood. If Saturn evolves to use async (likely for handling many concurrent beacon connections), the library integrates cleanly. Subprocess-based approaches would require manual async wrapping with `asyncio.create_subprocess_exec()`.

**6\. Proven in Production:** The fallback server already demonstrates this approach successfully. Home Assistant, Cura 3D printing software, and many IoT projects use python-zeroconf for exactly these reasons.

**Why NOT dns-sd subprocess:**

- macOS-only by default (linux requires avahi-utils)  
- Harder to test (mocking subprocesses vs mocking library calls)  
- No programmatic access to service info updates (must poll or re-run)  
- Version compatibility issues across OS releases

\---  
System Architecture

┌─────────────────────────────────────────────────────────┐  
│  DeepInfra Beacon Server                                │  
│  ├─ JWTManager: Mints & rotates scoped JWTs             │  
│  ├─ BeaconAnnouncer: mDNS with key in TXT record       │  
│  ├─ RotationScheduler: Background thread (every 5 min) │  
│  └─ FastAPI: /v1/health, /v1/models, /v1/chat/...     │  
└─────────────────────────────────────────────────────────┘  
│  
│ mDNS announcement  
│ \_saturn.\_tcp.local  
│ TXT: ephemeral\_key=jwt:eyJ...  
▼  
┌─────────────────────────────────────────────────────────┐  
│  Test Client (clients/beacon\_test\_client.py)           │  
│  ├─ BeaconListener: Discovers beacons via zeroconf     │  
│  ├─ Extract ephemeral\_key from TXT records             │  
│  └─ Call DeepInfra API DIRECTLY using extracted key   │  
└─────────────────────────────────────────────────────────┘

**NOTE:** beacon\_test\_client.py is a NEW FILE specifically for testing the beacon flow. It is NOT modifying an existing Saturn client. The purpose is to prove the end-to-end beacon concept works before integrating beacon discovery into existing clients like saturn\_client.py or the Open WebUI integration. This keeps the test isolated and simple.  
│  
│ HTTP POST  
│ Authorization: Bearer jwt:eyJ...  
▼  
┌─────────────────────────────────────────────────────────┐  
│  DeepInfra API ([https://api.deepinfra.com](https://api.deepinfra.com))             │  
│  └─ Validates ephemeral JWT, serves model response     │  
└─────────────────────────────────────────────────────────┘

Critical Design Choice: Client calls DeepInfra directly, not through beacon. Beacon is purely a credential dispenser. This proves "network presence \= automatic AI access without proxies."

\---  
Component Pseudocode

1\. JWTManager (Beacon Server)

```py

  class JWTManager:
      def __init__(self, rotation_interval=300):  # 5 minutes
          self.current_token = None
          self.expires_at = 0
          self.rotation_interval = rotation_interval
          self.lock = threading.Lock()

      def generate_token(self):
          """Call DeepInfra API to mint scoped JWT"""
          headers = {
              "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
              "Content-Type": "application/json"
          }
          payload = {
              "api_key_name": "auto",
              # Omit "models" → allows all models (Adam's requirement)
              "expires_delta": 600  # 10 min (buffer beyond 5 min rotation)
          }

          response = requests.post(
              "https://api.deepinfra.com/v1/scoped-jwt",
              headers=headers,
              json=payload,
              timeout=30
          )
          response.raise_for_status()

          token = response.json()["token"]  # Format: "jwt:eyJ..."

          with self.lock:
              self.current_token = token
              self.expires_at = time.time() + 600

          print(f"✓ Generated JWT (len={len(token)} chars, expires in 10 min)")
          return token

      def get_current_token(self):
          with self.lock:
              return self.current_token

      def needs_rotation(self):
          """Rotate every 5 min OR if token about to expire"""
          with self.lock:
              time_until_expiry = self.expires_at - time.time()
              return time_until_expiry <= self.rotation_interval
```

\---  
2\. BeaconAnnouncer (Beacon Server)

```py

  class BeaconAnnouncer:
      def __init__(self, port, priority, jwt_manager):
          self.port = port
          self.priority = priority
          self.jwt_manager = jwt_manager
          self.zeroconf = None
          self.service_info = None

      def register(self):
          """Register/re-register mDNS service with current JWT"""
          token = self.jwt_manager.get_current_token()

          # Unregister previous if exists (for rotation)
          if self.zeroconf:
              self.unregister()

          self.zeroconf = Zeroconf()

          host = socket.gethostname()
          host_ip = socket.gethostbyname(host)
          service_name = "DeepInfra-Beacon._saturn._tcp.local."

          # CRITICAL: Check TXT record size limit (~250 chars)
          if len(token) > 240:
              print(f"⚠️  WARNING: Token is {len(token)} chars!")
              print(f"⚠️  May exceed mDNS TXT record limit (~250 chars)")
              # Memo warned us about this - log but try anyway

          self.service_info = ServiceInfo(
              type_="_saturn._tcp.local.",
              name=service_name,
              port=self.port,
              addresses=[socket.inet_aton(host_ip)],
              server=f"{host}.local.",
              properties={
                  'version': '1.0',
                  'api': 'DeepInfra',
                  'priority': str(self.priority),
                  'ephemeral_key': token,  # ← THE MAGIC
                  'rotation_interval': '300',  # Tell clients refresh rate
                  'features': 'ephemeral-credentials,auto-rotation'
              }
          )

          self.zeroconf.register_service(self.service_info)
          print(f"✓ Beacon registered with ephemeral key in TXT")

      def unregister(self):
          if self.zeroconf and self.service_info:
              self.zeroconf.unregister_service(self.service_info)
              self.zeroconf.close()
              self.zeroconf = None
              self.service_info = None
```

\---  
3\. Rotation Loop (Beacon Server)

```py
  def rotation_loop(jwt_manager, beacon_announcer):
      """Background thread: rotate keys every 5 minutes"""
      while True:
          time.sleep(60)  # Check every minute

          if jwt_manager.needs_rotation():
              print("\n🔄 Rotating ephemeral key...")
              jwt_manager.generate_token()
              beacon_announcer.register()  # mDNS update with new key
              print("✓ Rotation complete\n")
```

—  
4\. Beacon Server Main

```py

  def main():
      parser = argparse.ArgumentParser()
      parser.add_argument("--host", default="0.0.0.0")
      parser.add_argument("--port", type=int, default=8090)
      parser.add_argument("--priority", type=int, default=10)  # High priority
      args = parser.parse_args()

      # Step 1: Generate first JWT
      jwt_manager = JWTManager(rotation_interval=300)
      jwt_manager.generate_token()

      # Step 2: Register mDNS with first JWT
      beacon_announcer = BeaconAnnouncer(args.port, args.priority, jwt_manager)
      beacon_announcer.register()

      # Step 3: Start rotation thread
      rotation_thread = threading.Thread(
          target=rotation_loop,
          args=(jwt_manager, beacon_announcer),
          daemon=True
      )
      rotation_thread.start()

      # Step 4: Start FastAPI server
      try:
          uvicorn.run(app, host=args.host, port=args.port)
      finally:
          beacon_announcer.unregister()
```

\---  
5\. Client Discovery (Modified Client)

```py

  class BeaconListener(ServiceListener):
      def __init__(self):
          self.beacons = {}  # name → {url, priority, ephemeral_key, ...}
          self.lock = threading.Lock()
          self.beacon_found = threading.Event()

      def add_service(self, zc: Zeroconf, type_: str, name: str):
          """Called when beacon discovered OR when TXT records update"""
          info = zc.get_service_info(type_, name)
          if not info:
              return

          # Extract ephemeral key from TXT records
          ephemeral_key_bytes = info.properties.get(b'ephemeral_key')
          if not ephemeral_key_bytes:
              return  # Not a beacon, skip

          ephemeral_key = ephemeral_key_bytes.decode('utf-8')

          with self.lock:
              address = socket.inet_ntoa(info.addresses[0])
              port = info.port
              url = f"http://{address}:{port}"
              priority = int(info.properties.get(b'priority', b'50').decode('utf-8'))
              rotation_interval = int(info.properties.get(b'rotation_interval', b'300').decode('utf-8'))

              clean_name = name.replace('._saturn._tcp.local.', '')
              self.beacons[clean_name] = {
                  'url': url,
                  'priority': priority,
                  'ephemeral_key': ephemeral_key,
                  'rotation_interval': rotation_interval,
                  'discovered_at': time.time()
              }

              print(f"✓ Discovered beacon: {clean_name}")
              print(f"  URL: {url}")
              print(f"  Key: {ephemeral_key[:60]}...")
              print(f"  Rotation: every {rotation_interval}s")

              self.beacon_found.set()

      def update_service(self, zc: Zeroconf, type_: str, name: str):
          """Called when beacon updates TXT records (KEY ROTATION!)"""
          print(f"🔄 Beacon updated: {name}")
          self.add_service(zc, type_, name)  # Re-extract new key

      def remove_service(self, zc: Zeroconf, type_: str, name: str):
          clean_name = name.replace('._saturn._tcp.local.', '')
          with self.lock:
              if clean_name in self.beacons:
                  del self.beacons[clean_name]
                  print(f"✗ Beacon removed: {clean_name}")

      def get_best_beacon(self):
          """Return lowest priority beacon"""
          with self.lock:
              if not self.beacons:
                  return None
              return min(self.beacons.values(), key=lambda b: b['priority'])
```

\---  
6\. Client API Call (Modified Client)

```py
  def chat_with_deepinfra(ephemeral_key, model, user_message):
      """Call DeepInfra DIRECTLY using ephemeral key from beacon"""

      DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/chat/completions"

      headers = {
          "Authorization": f"Bearer {ephemeral_key}",  # ← Extracted from mDNS
          "Content-Type": "application/json"
      }

      payload = {
          "model": model,
          "messages": [{"role": "user", "content": user_message}]
      }

      print(f"\n→ Calling DeepInfra API directly...")
      print(f"  Model: {model}")
      print(f"  Using ephemeral key: {ephemeral_key[:60]}...")

      response = requests.post(DEEPINFRA_API_URL, headers=headers, json=payload, timeout=60)

      if response.ok:
          result = response.json()
          content = result['choices'][0]['message']['content']
          print(f"✓ Success! Response: {content[:100]}...")
          return content
      else:
          print(f"✗ Error: {response.status_code}")
          print(f"  {response.text}")
          return None

```

\---  
Configuration Parameters

Beacon Server:  
\- Rotation interval: 5 minutes (300 seconds)  
\- JWT expiration: 10 minutes (600 seconds) \- buffer to prevent gaps  
\- Default priority: 10 (high priority to be selected first)  
\- Default port: 8090 (avoid conflicts with existing Saturn servers)

Client:  
\- Discovery timeout: 5 seconds initial scan  
\- Keep ServiceBrowser running to detect key rotation updates  
\- No caching needed \- always use current key from listener

\---  
Testing Plan

Phase 1: JWT Generation (Manual)

```shell

  curl -X POST "https://api.deepinfra.com/v1/scoped-jwt" \
    -H "Authorization: Bearer $DEEPINFRA_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"api_key_name": "auto", "expires_delta": 600}'
```

Verify:  
\- Response contains {"token": "jwt:..."}  
\- Token length (check if \<250 chars)  
\- Token can be used for API calls

\---  
Phase 2: Beacon Server Startup

python servers/deepinfra\_beacon.py \--priority 10 \--port 8090

Verify:  
\- JWT generated successfully  
\- mDNS registration succeeds  
\- Check with: dns-sd \-B \_saturn.\_tcp local  
\- Lookup TXT: dns-sd \-L DeepInfra-Beacon \_saturn.\_tcp local  
\- Confirm ephemeral\_key appears in TXT records

\---  
Phase 3: Client Discovery

python clients/beacon\_test\_client.py

Verify:  
\- Client discovers beacon within 5 seconds  
\- Extracts ephemeral key from TXT records  
\- Prints key (first 60 chars)

\---  
Phase 4: Direct API Call

Client makes request to DeepInfra using extracted key

Verify:  
\- Request succeeds  
\- Response received  
\- No errors about invalid credentials

\---  
Phase 5: Key Rotation (Wait 5 Minutes)

Verify:  
\- Beacon logs "🔄 Rotating ephemeral key..."  
\- New JWT generated  
\- mDNS re-registers  
\- Client's update\_service() callback fires  
\- Client logs "🔄 Beacon updated"  
\- Client extracts new key  
\- Old key (saved separately) now fails API calls  
\- New key succeeds

\---  
Phase 6: Key Expiration (Wait 10 Minutes)

Verify:  
\- Expired key rejected by DeepInfra  
\- Client using fresh key still works

\---  
Edge Cases & Mitigations

| Edge Case | Mitigation |
| :---- | :---- |
| JWT \>250 chars | Log warning, try anyway. If truncated, fallback to HTTP /v1/ephemeral-key endpoint |
| DeepInfra API rate limits | Catch 429 errors, exponential backoff on rotation |
| Network drops during rotation | Try/except on mDNS register, retry logic |
| Multiple clients | All share same ephemeral key (intended behavior) |
| Client arrives mid-cycle | Gets current key immediately, valid for 5+ more minutes |
| Beacon crashes | Clients lose access until restart (acceptable for Sprint 1\) |

\---  
Success Criteria (Sprint 1 Definition of Done)

✅ Beacon generates DeepInfra scoped JWT with expires\_delta=600, all models allowed

✅ Beacon announces via mDNS with ephemeral\_key in TXT record, service type \_saturn.\_tcp.local

✅ Beacon rotates key every 5 minutes and updates mDNS announcement

✅ Client discovers beacon via zeroconf within 5 seconds

✅ Client extracts ephemeral key from TXT properties

✅ Client makes successful API call to DeepInfra using extracted key (not through beacon proxy)

✅ Client detects key rotation via update\_service() callback, extracts new key

✅ Old keys expire and are rejected by DeepInfra after 10 minutes

✅ End-to-end demo: Beacon running → Client discovers → Client chats using ephemeral key → Key rotates → Client updates → Old key fails → New key works

\---  
Deliverables

1\. beacons/deepinfra\_beacon.py \- Fully functional beacon server (NEW FILE) 2\. clients/beacon\_test\_client.py \- Demo client proving end-to-end flow (NEW FILE \- standalone test, not modifying existing clients) 3\. Documentation \- README section explaining beacon usage  
4\. Test script \- Automated verification of all success criteria  
5\. Demo video/screenshots \- For Adam to see proof of concept

**Future Work (Post-Sprint 1):** Once beacon\_test\_client.py proves the concept works, integrate beacon discovery into the existing Saturn clients (saturn\_client.py, Open WebUI integration, etc.) as a second step.

\---  
Why This Proves The Vision

Adam's Requirements: ✅ All met

What This Demonstrates:  
\- ✅ Network presence \= automatic access (zero manual key distribution)  
\- ✅ Leave network \= credentials expire (security by design)  
\- ✅ Zero-configuration workflow (pure mDNS, no config files)  
\- ✅ Time-limited access without manual revocation  
\- ✅ Foundation for Layer 2 (budgeting, metering) and Layer 3 (coordination)

The Cornerstone: Once this works, we can add:  
\- Token consumption tracking (agents see costs)  
\- Budget enforcement (agents manage allocation)  
\- Presence broadcasting (agents see each other)  
\- Spawn protocol (agents delegate to subordinates)  
\- Reputation service (performance tracking)

Sprint 1 is the foundation. Get it right, and the robot factory becomes possible.