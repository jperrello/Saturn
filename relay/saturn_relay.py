import os
import time
import hashlib
import secrets
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(
    title="Saturn Relay",
    description="Minimal coordination service for Saturn beacons",
    version="0.1.0"
)

RELAY_SECRET = os.getenv("RELAY_SECRET", "saturn-dev-secret")
BEACON_TTL_SECONDS = 600  # Beacons expire after 10 min without heartbeat

beacons: dict = {}


class BeaconRegistration(BaseModel):
    beacon_id: str
    ephemeral_key: str
    provider: str = "openrouter"
    models: list[str] = []


class BeaconInfo(BaseModel):
    beacon_id: str
    ephemeral_key: str
    provider: str
    models: list[str]
    registered_at: str
    last_seen: str
    key_fingerprint: str


def verify_secret(authorization: Optional[str]) -> bool:
    if not authorization:
        return False
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        return secrets.compare_digest(token, RELAY_SECRET)
    return False


def key_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def cleanup_stale_beacons():
    now = time.time()
    stale = [bid for bid, b in beacons.items() if now - b["last_seen_ts"] > BEACON_TTL_SECONDS]
    for bid in stale:
        del beacons[bid]


@app.get("/")
def root():
    return {
        "service": "Saturn Relay",
        "version": "0.1.0",
        "endpoints": {
            "POST /register": "Register/update a beacon (requires auth)",
            "GET /beacon/{beacon_id}": "Get beacon info",
            "GET /beacons": "List all active beacons",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
def health():
    return {"status": "ok", "beacons_registered": len(beacons)}


@app.post("/register")
def register_beacon(
    registration: BeaconRegistration,
    authorization: Optional[str] = Header(None)
):
    if not verify_secret(authorization):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization")
    
    cleanup_stale_beacons()
    
    now = datetime.utcnow().isoformat() + "Z"
    now_ts = time.time()
    
    is_new = registration.beacon_id not in beacons
    
    beacons[registration.beacon_id] = {
        "beacon_id": registration.beacon_id,
        "ephemeral_key": registration.ephemeral_key,
        "provider": registration.provider,
        "models": registration.models,
        "registered_at": beacons.get(registration.beacon_id, {}).get("registered_at", now),
        "last_seen": now,
        "last_seen_ts": now_ts,
    }
    
    return {
        "status": "registered" if is_new else "updated",
        "beacon_id": registration.beacon_id,
        "key_fingerprint": key_fingerprint(registration.ephemeral_key),
        "expires_in_seconds": BEACON_TTL_SECONDS
    }


@app.delete("/beacon/{beacon_id}")
def unregister_beacon(
    beacon_id: str,
    authorization: Optional[str] = Header(None)
):
    if not verify_secret(authorization):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization")
    
    if beacon_id not in beacons:
        raise HTTPException(status_code=404, detail="Beacon not found")
    
    del beacons[beacon_id]
    return {"status": "unregistered", "beacon_id": beacon_id}


@app.get("/beacon/{beacon_id}")
def get_beacon(beacon_id: str) -> BeaconInfo:
    cleanup_stale_beacons()
    
    if beacon_id not in beacons:
        raise HTTPException(status_code=404, detail="Beacon not found")
    
    b = beacons[beacon_id]
    return BeaconInfo(
        beacon_id=b["beacon_id"],
        ephemeral_key=b["ephemeral_key"],
        provider=b["provider"],
        models=b["models"],
        registered_at=b["registered_at"],
        last_seen=b["last_seen"],
        key_fingerprint=key_fingerprint(b["ephemeral_key"])
    )


@app.get("/beacons")
def list_beacons() -> list[BeaconInfo]:
    cleanup_stale_beacons()
    
    result = []
    for b in beacons.values():
        result.append(BeaconInfo(
            beacon_id=b["beacon_id"],
            ephemeral_key=b["ephemeral_key"],
            provider=b["provider"],
            models=b["models"],
            registered_at=b["registered_at"],
            last_seen=b["last_seen"],
            key_fingerprint=key_fingerprint(b["ephemeral_key"])
        ))
    
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8888))
    uvicorn.run(app, host="0.0.0.0", port=port)
