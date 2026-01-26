# Saturn Relay

Minimal coordination service for Saturn beacons. Lets you access your home AI from anywhere.

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Beacon    │──────►│   Relay     │◄──────│   Client    │
│  (home)     │ POST  │  (cloud)    │  GET  │  (Bali)     │
│             │register             │beacon │             │
└─────────────┘       └─────────────┘       └─────────────┘
                            │
                            │ returns ephemeral key
                            ▼
                      ┌─────────────┐
                      │ OpenRouter  │  ◄── client calls directly
                      │ /DeepInfra  │
                      └─────────────┘
```

## Quick Start (Local)

```bash
cd relay
pip install -r requirements.txt
python saturn_relay.py
```

Server runs at http://localhost:8888

## Deploy to Render (Free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repo, select the `relay` directory
4. Render auto-detects `render.yaml` and deploys
5. Copy your RELAY_SECRET from the environment tab

Your relay will be at: `https://saturn-relay-xxxx.onrender.com`

## API Endpoints

### Register a beacon (requires auth)
```bash
curl -X POST https://your-relay.onrender.com/register \
  -H "Authorization: Bearer YOUR_RELAY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "beacon_id": "joey-home",
    "ephemeral_key": "sk-or-v1-abc123...",
    "provider": "openrouter",
    "models": ["meta-llama/llama-3-70b"]
  }'
```

### Get a beacon (no auth needed)
```bash
curl https://your-relay.onrender.com/beacon/joey-home
```

Response:
```json
{
  "beacon_id": "joey-home",
  "ephemeral_key": "sk-or-v1-abc123...",
  "provider": "openrouter",
  "models": ["meta-llama/llama-3-70b"],
  "registered_at": "2025-01-17T12:00:00Z",
  "last_seen": "2025-01-17T12:05:00Z",
  "key_fingerprint": "a1b2c3d4e5f6"
}
```

### List all beacons
```bash
curl https://your-relay.onrender.com/beacons
```

### Health check
```bash
curl https://your-relay.onrender.com/health
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RELAY_SECRET` | `saturn-dev-secret` | Shared secret for beacon auth |
| `PORT` | `8888` | Server port |

## Security Notes

- Beacons need the secret to register (prevents spam)
- Clients can read beacon info without auth (the ephemeral key IS the auth for the AI provider)
- Ephemeral keys auto-rotate at the beacon, relay just reflects current state
- Beacons expire after 10 minutes without heartbeat

## For Beacon Operators

Add this to your beacon to push to the relay every key rotation:

```python
import requests

RELAY_URL = "https://your-relay.onrender.com"
RELAY_SECRET = "your-secret"

def push_to_relay(beacon_id: str, ephemeral_key: str, provider: str = "openrouter"):
    requests.post(
        f"{RELAY_URL}/register",
        headers={"Authorization": f"Bearer {RELAY_SECRET}"},
        json={
            "beacon_id": beacon_id,
            "ephemeral_key": ephemeral_key,
            "provider": provider
        }
    )
```

## For Clients

Query the relay when mDNS discovery fails:

```python
import requests

RELAY_URL = "https://your-relay.onrender.com"

def get_remote_beacon(beacon_id: str):
    resp = requests.get(f"{RELAY_URL}/beacon/{beacon_id}")
    if resp.ok:
        return resp.json()
    return None

# Use the key to call OpenRouter directly
beacon = get_remote_beacon("joey-home")
if beacon:
    key = beacon["ephemeral_key"]
    # Now call OpenRouter with this key
```
