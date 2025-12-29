# Saturn Beacon - DeepInfra Ephemeral Credentials

Saturn Beacon provides automatic network-level access to AI services using ephemeral credentials distributed via mDNS.

## Architecture

The beacon system consists of:

1. **JWTManager** - Generates scoped JWT tokens from DeepInfra API
2. **BeaconAnnouncer** - Announces service via mDNS with ephemeral key in TXT records
3. **KeyRotation** - Background thread that rotates credentials every 5 minutes
4. **DeepInfra Beacon Server** - FastAPI server that coordinates all components

## How It Works

1. Beacon server generates a scoped JWT from DeepInfra API (expires in 10 minutes)
2. JWT is embedded in mDNS TXT record under `ephemeral_key`
3. Beacon announces itself as `_saturn._tcp.local.` service
4. Clients discover beacon via mDNS and extract ephemeral key
5. Clients call DeepInfra API DIRECTLY using the ephemeral key (not through beacon)
6. Every 5 minutes, beacon rotates to a new JWT and updates mDNS announcement
7. Clients detect TXT record update and automatically use new key

## Key Design Principle

**The beacon is a credential dispenser, not a proxy.** Clients get ephemeral keys from the beacon but make API calls directly to DeepInfra. This proves "network presence = automatic AI access" without adding a proxy layer.

## Running the Beacon Server

### Prerequisites

```bash
export DEEPINFRA_API_KEY="your_api_key_here"
pip install fastapi uvicorn zeroconf requests
```

### Start the Server

```bash
cd beacons
python deepinfra_beacon.py --port 8090 --priority 10
```

Options:
- `--host` - Host to bind to (default: 0.0.0.0)
- `--port` - Port to bind to (default: 8090)
- `--priority` - Beacon priority, lower is higher priority (default: 10)

### Verify via mDNS

```bash
# Browse for services
dns-sd -B _saturn._tcp local

# Lookup specific service
dns-sd -L DeepInfra-Beacon _saturn._tcp local
```

## Configuration

- **JWT Expiration**: 600 seconds (10 minutes)
- **Rotation Interval**: 300 seconds (5 minutes)
- **Service Type**: `_saturn._tcp.local.`
- **Default Priority**: 10

## File Structure

### beacons/deepinfra_beacon.py
Single-file beacon server containing all components:
- **JWTManager class**: Generates and manages scoped JWTs from DeepInfra API with automatic rotation tracking
- **BeaconAnnouncer class**: Registers and updates mDNS announcements using zeroconf library with ephemeral key in TXT records  
- **rotation_loop function**: Background thread that checks every minute and rotates keys every 5 minutes with error handling for network failures and rate limits
- **FastAPI app**: Health check and model listing endpoints

### clients/beacon_client.py
Test client demonstrating beacon discovery and usage:
- **BeaconListener class**: Discovers Saturn beacons via zeroconf ServiceBrowser callbacks
- **chat_with_deepinfra function**: Makes direct API calls to DeepInfra using ephemeral credentials
- **main function**: End-to-end test: discover beacon → extract key → call API → monitor rotation

## Security Model

- Credentials expire automatically after 10 minutes
- New credentials generated every 5 minutes (buffer prevents gaps)
- Leave network = lose access (mDNS is local-only)
- No long-lived credentials stored on client devices
- All clients share the same ephemeral key (intended behavior for network-level access)

## Why Zeroconf Library?

We use the Python `zeroconf` library instead of `dns-sd` subprocess because:

1. **Dynamic TXT Updates**: Key rotation requires updating TXT records every few minutes. With zeroconf, we call `unregister_service()` then `register_service()` - clean and atomic.
2. **Cross-Platform**: Works on macOS, Linux, and Windows without requiring dns-sd binary.
3. **Native Python**: Direct property dictionary access, proper exceptions, no subprocess parsing.
4. **Error Handling**: Raises proper Python exceptions instead of opaque exit codes.
5. **Production Proven**: Used by Home Assistant, Cura, and many IoT projects.

## Endpoints

### GET /v1/health
Returns beacon health status and token information.

### GET /v1/models
Returns list of available DeepInfra models.

## Success Criteria

- ✓ Beacon generates DeepInfra scoped JWT with 600s expiration
- ✓ Beacon announces via mDNS with ephemeral_key in TXT record
- ✓ Beacon rotates key every 5 minutes and updates mDNS
- ✓ Clients discover beacon via zeroconf within 5 seconds
- ✓ Clients extract ephemeral key from TXT properties
- ✓ Clients make successful API calls to DeepInfra using extracted key
- ✓ Clients detect key rotation via update_service() callback
- ✓ Old keys expire and are rejected after 10 minutes

## Troubleshooting

**Beacon won't start:**
- Ensure DEEPINFRA_API_KEY is set
- Check port 8090 is available
- Verify zeroconf library is installed

**Clients can't discover beacon:**
- Ensure firewall allows mDNS (UDP port 5353)
- Check beacon is running and registered
- Try `dns-sd -B _saturn._tcp local` to verify announcement

**API calls fail:**
- Check ephemeral key is being extracted correctly
- Verify key hasn't expired (check timestamp)
- Ensure network connectivity to api.deepinfra.com

**Keys not rotating:**
- Check beacon logs for rotation events
- Verify rotation thread is running
- Check for API rate limit errors (429)
