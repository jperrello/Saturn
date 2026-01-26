import os
import logging
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

RELAY_URL = os.getenv("SATURN_RELAY_URL", "")
RELAY_SECRET = os.getenv("SATURN_RELAY_SECRET", "")


@dataclass
class RemoteBeacon:
    beacon_id: str
    ephemeral_key: str
    provider: str
    models: list
    last_seen: str
    key_fingerprint: str


class RelayPublisher:
    def __init__(
        self,
        relay_url: str,
        relay_secret: str,
        beacon_id: str,
        provider: str = "openrouter",
        heartbeat_interval: int = 60
    ):
        self.relay_url = relay_url.rstrip("/")
        self.relay_secret = relay_secret
        self.beacon_id = beacon_id
        self.provider = provider
        self.heartbeat_interval = heartbeat_interval
        self._current_key: Optional[str] = None
        self._models: list = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.relay_secret}",
            "Content-Type": "application/json"
        }

    def publish(self, ephemeral_key: str, models: list = None):
        self._current_key = ephemeral_key
        if models:
            self._models = models
        
        try:
            resp = requests.post(
                f"{self.relay_url}/register",
                headers=self._headers(),
                json={
                    "beacon_id": self.beacon_id,
                    "ephemeral_key": ephemeral_key,
                    "provider": self.provider,
                    "models": self._models
                },
                timeout=10
            )
            if resp.ok:
                data = resp.json()
                logger.info(f"Published to relay: {self.beacon_id} (fingerprint: {data.get('key_fingerprint', 'unknown')})")
                return True
            else:
                logger.warning(f"Relay publish failed: {resp.status_code} - {resp.text}")
                return False
        except requests.RequestException as e:
            logger.warning(f"Relay publish error: {e}")
            return False

    def unregister(self):
        try:
            resp = requests.delete(
                f"{self.relay_url}/beacon/{self.beacon_id}",
                headers=self._headers(),
                timeout=10
            )
            if resp.ok:
                logger.info(f"Unregistered from relay: {self.beacon_id}")
            return resp.ok
        except requests.RequestException as e:
            logger.warning(f"Relay unregister error: {e}")
            return False

    def _heartbeat_loop(self):
        while self._running:
            if self._current_key:
                self.publish(self._current_key)
            time.sleep(self.heartbeat_interval)

    def start_heartbeat(self):
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info(f"Relay heartbeat started (every {self.heartbeat_interval}s)")

    def stop_heartbeat(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


class RelayClient:
    def __init__(self, relay_url: str):
        self.relay_url = relay_url.rstrip("/")

    def get_beacon(self, beacon_id: str) -> Optional[RemoteBeacon]:
        try:
            resp = requests.get(f"{self.relay_url}/beacon/{beacon_id}", timeout=10)
            if resp.ok:
                data = resp.json()
                return RemoteBeacon(
                    beacon_id=data["beacon_id"],
                    ephemeral_key=data["ephemeral_key"],
                    provider=data["provider"],
                    models=data.get("models", []),
                    last_seen=data["last_seen"],
                    key_fingerprint=data["key_fingerprint"]
                )
            return None
        except requests.RequestException as e:
            logger.warning(f"Relay lookup error: {e}")
            return None

    def list_beacons(self) -> list[RemoteBeacon]:
        try:
            resp = requests.get(f"{self.relay_url}/beacons", timeout=10)
            if resp.ok:
                return [
                    RemoteBeacon(
                        beacon_id=b["beacon_id"],
                        ephemeral_key=b["ephemeral_key"],
                        provider=b["provider"],
                        models=b.get("models", []),
                        last_seen=b["last_seen"],
                        key_fingerprint=b["key_fingerprint"]
                    )
                    for b in resp.json()
                ]
            return []
        except requests.RequestException as e:
            logger.warning(f"Relay list error: {e}")
            return []

    def health(self) -> bool:
        try:
            resp = requests.get(f"{self.relay_url}/health", timeout=5)
            return resp.ok
        except requests.RequestException:
            return False
